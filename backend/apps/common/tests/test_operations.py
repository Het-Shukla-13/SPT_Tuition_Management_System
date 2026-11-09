"""Phase 8a: backups, restore guard, scheduler, cleanup, proxy-aware client IPs."""

from datetime import datetime, time, timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import OTPChallenge, User, UserSession
from apps.accounts.services.sms import DisabledSMSBackend, SMSDeliveryError
from apps.common import backups
from apps.common.management.commands.run_scheduler import next_run, parse_at, run_job
from apps.common.request_utils import client_ip

IST = ZoneInfo("Asia/Kolkata")


# ── client IP behind the proxy ─────────────────────────────────────────────
class TestClientIp:
    def _request(self, xff=None):
        meta = {"REMOTE_ADDR": "172.18.0.5"}  # Caddy's container address
        if xff:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().get("/", **meta)

    def test_without_trusted_proxy_forwarded_header_is_ignored(self, settings):
        settings.TRUSTED_PROXY_COUNT = 0
        assert client_ip(self._request("1.2.3.4")) == "172.18.0.5"

    def test_one_proxy_uses_the_entry_it_appended(self, settings):
        settings.TRUSTED_PROXY_COUNT = 1
        assert client_ip(self._request("49.36.1.1")) == "49.36.1.1"

    def test_client_cannot_spoof_by_prepending_addresses(self, settings):
        settings.TRUSTED_PROXY_COUNT = 1
        # Attacker sends "X-Forwarded-For: 9.9.9.9"; the proxy appends the real IP.
        assert client_ip(self._request("9.9.9.9, 49.36.1.1")) == "49.36.1.1"

    def test_missing_header_falls_back_to_remote_addr(self, settings):
        settings.TRUSTED_PROXY_COUNT = 1
        assert client_ip(self._request()) == "172.18.0.5"


# ── scheduler timing ───────────────────────────────────────────────────────
class TestScheduler:
    def test_later_today(self):
        now = datetime(2026, 11, 8, 1, 0, tzinfo=IST)
        assert next_run(time(2, 30), now) == datetime(2026, 11, 8, 2, 30, tzinfo=IST)

    def test_already_passed_today_runs_tomorrow(self):
        now = datetime(2026, 11, 8, 2, 30, tzinfo=IST)  # exactly at the time: not again
        assert next_run(time(2, 30), now) == datetime(2026, 11, 9, 2, 30, tzinfo=IST)

    def test_month_end_rollover(self):
        now = datetime(2026, 11, 30, 23, 0, tzinfo=IST)
        assert next_run(parse_at("02:30"), now) == datetime(
            2026, 12, 1, 2, 30, tzinfo=IST
        )

    @pytest.mark.django_db
    def test_failing_job_is_reported_not_raised(self):
        with mock.patch(
            "apps.common.management.commands.run_scheduler.call_command",
            side_effect=RuntimeError("boom"),
        ):
            assert run_job("backup_database") is False

    def test_jobs_configured_are_real_commands(self, settings):
        from django.core.management import get_commands

        for job in settings.SCHEDULED_JOBS:
            assert job["command"] in get_commands()
            parse_at(job["at"])


# ── cleanup ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_purge_keeps_recent_and_active_records(settings):
    settings.OTP_RETENTION_DAYS = settings.SESSION_RETENTION_DAYS = 90
    now = timezone.now()
    user = User.objects.create_user(email="p@example.com")

    def otp(age_days, ident):
        o = OTPChallenge.objects.create(
            channel="EMAIL",
            identifier=ident,
            purpose="LOGIN",
            code_hash="x",
            expires_at=now,
            max_attempts=5,
            invalidated_at=now,
        )
        OTPChallenge.objects.filter(pk=o.pk).update(
            created_at=now - timedelta(days=age_days)
        )
        return o

    old_otp, new_otp = otp(91, "a@example.com"), otp(10, "b@example.com")

    def session(sid, **kw):
        return UserSession.objects.create(
            user=user, session_id=sid, refresh_token_jti=sid, **kw
        )

    old_revoked = session("s1", expires_at=now, revoked_at=now - timedelta(days=100))
    old_expired = session("s2", expires_at=now - timedelta(days=95))
    recent_revoked = session(
        "s3", expires_at=now + timedelta(days=5), revoked_at=now - timedelta(days=1)
    )
    active = session("s4", expires_at=now + timedelta(days=5))

    out = StringIO()
    call_command("purge_expired_records", stdout=out)

    assert not OTPChallenge.objects.filter(pk=old_otp.pk).exists()
    assert OTPChallenge.objects.filter(pk=new_otp.pk).exists()
    remaining = set(UserSession.objects.values_list("pk", flat=True))
    assert remaining == {recent_revoked.pk, active.pk}
    assert old_revoked.pk not in remaining and old_expired.pk not in remaining
    assert "1 OTP challenges and 2 ended sessions" in out.getvalue()


# ── backups ────────────────────────────────────────────────────────────────
def _fake_pg(writes: bytes = b"PGDMP-data", returncode: int = 0):
    calls = []

    def run(cmd, env, **kwargs):
        calls.append((cmd, env))
        if "--file" in cmd and returncode == 0:
            with open(cmd[cmd.index("--file") + 1], "wb") as fh:
                fh.write(writes)
        return SimpleNamespace(returncode=returncode, stderr="connection refused")

    return run, calls


@pytest.mark.django_db
class TestBackupCommand:
    @pytest.fixture(autouse=True)
    def _setup(self, settings, tmp_path):
        settings.BACKUP_DIR = tmp_path
        settings.BACKUP_KEEP = 2
        settings.BACKUP_TO_DRIVE = False
        with mock.patch.object(
            backups.shutil, "which", return_value="/usr/bin/pg_dump"
        ):
            yield

    def test_dump_written_password_not_on_command_line(self, tmp_path):
        run, calls = _fake_pg()
        password = "s3cr3t-db-pw"
        with (
            mock.patch.object(backups.subprocess, "run", side_effect=run),
            mock.patch.dict(connection.settings_dict, {"PASSWORD": password}),
        ):
            call_command("backup_database", stdout=StringIO())
        dumps = list(tmp_path.glob("db-backup-*.dump"))
        assert len(dumps) == 1 and dumps[0].read_bytes() == b"PGDMP-data"
        cmd, env = calls[0]
        assert "--format=custom" in cmd
        assert env["PGPASSWORD"] == password
        assert all(password not in part for part in cmd)

    def test_keeps_only_the_newest(self, tmp_path):
        for name in [
            "db-backup-20260101-000000.dump",
            "db-backup-20260102-000000.dump",
        ]:
            (tmp_path / name).write_bytes(b"old")
        run, _ = _fake_pg()
        with mock.patch.object(backups.subprocess, "run", side_effect=run):
            call_command("backup_database", stdout=StringIO())
        names = sorted(p.name for p in tmp_path.glob("db-backup-*.dump"))
        assert len(names) == 2 and "db-backup-20260101-000000.dump" not in names

    def test_failure_raises_and_leaves_no_partial_file(self, tmp_path):
        run, _ = _fake_pg(returncode=1)
        with mock.patch.object(backups.subprocess, "run", side_effect=run):
            with pytest.raises(CommandError, match="connection refused"):
                call_command("backup_database", stdout=StringIO())
        assert not list(tmp_path.glob("*.dump"))

    def test_uploads_to_drive_and_prunes_old_drive_copies(self, settings):
        settings.BACKUP_TO_DRIVE = True
        run, _ = _fake_pg()
        drive = mock.Mock()
        drive.list_files.return_value = ["gdrive/new", "gdrive/mid", "gdrive/old"]
        with (
            mock.patch.object(backups.subprocess, "run", side_effect=run),
            mock.patch(
                "apps.common.management.commands.backup_database.drive_configured",
                return_value=True,
            ),
            mock.patch(
                "apps.common.management.commands.backup_database.GoogleDriveStorage",
                return_value=drive,
            ),
        ):
            call_command("backup_database", stdout=StringIO())
        drive.save.assert_called_once()
        drive.delete.assert_called_once_with("gdrive/old")


@pytest.mark.django_db
class TestRestoreGuard:
    def test_requires_typing_the_database_name(self, tmp_path):
        dump = tmp_path / "x.dump"
        dump.write_bytes(b"PGDMP")
        with mock.patch.object(backups, "restore_database") as restore:
            with pytest.raises(CommandError, match="--confirm"):
                call_command("restore_database", str(dump), confirm="wrong-db")
            restore.assert_not_called()

    def test_restores_with_correct_confirmation(self, tmp_path):
        dump = tmp_path / "x.dump"
        dump.write_bytes(b"PGDMP")
        target = "apps.common.management.commands.restore_database.restore_database"
        with mock.patch(target) as restore:
            call_command(
                "restore_database",
                str(dump),
                confirm=connection.settings_dict["NAME"],
                stdout=StringIO(),
            )
        restore.assert_called_once()


# ── production safety ──────────────────────────────────────────────────────
def test_disabled_sms_backend_fails_cleanly():
    with pytest.raises(SMSDeliveryError):
        DisabledSMSBackend().send("+919000000001", "123456 is your code")
