"""
Database backup and restore with the PostgreSQL client tools.

- Dumps use pg_dump's "custom" format: compressed, and restorable with
  pg_restore (whole database or selected tables).
- The database password is passed through the PGPASSWORD environment variable,
  never on the command line, where `ps` would show it to other users.
- pg_dump refuses to dump a server newer than itself, so the client tools
  must be version 18+ (the Docker image installs them from PostgreSQL's apt repo).
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.utils import timezone

BACKUP_PREFIX = "db-backup-"
BACKUP_SUFFIX = ".dump"


class BackupError(Exception):
    pass


def _tool(name: str) -> str:
    path = shutil.which(name, path=settings.PG_BIN_DIR or None)
    if not path:
        raise BackupError(
            f"`{name}` not found. Install the PostgreSQL 18 client tools or set PG_BIN_DIR."
        )
    return path


def _connection_args() -> tuple[list[str], dict]:
    db = connections["default"].settings_dict
    args = [
        "--host",
        db.get("HOST") or "localhost",
        "--port",
        str(db.get("PORT") or 5432),
    ]
    args += ["--username", db["USER"]]
    env = {
        **os.environ,
        "PGPASSWORD": db.get("PASSWORD") or "",
        "PGCONNECT_TIMEOUT": "10",
    }
    return args, env


def _run(cmd: list[str], env: dict) -> None:
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise BackupError(f"{Path(cmd[0]).name} failed: {result.stderr.strip()[:1000]}")


def backup_filename(now: datetime | None = None) -> str:
    now = timezone.localtime(now or timezone.now())
    return f"{BACKUP_PREFIX}{now:%Y%m%d-%H%M%S}{BACKUP_SUFFIX}"


def dump_database(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / backup_filename()
    args, env = _connection_args()
    db_name = connections["default"].settings_dict["NAME"]
    cmd = [_tool("pg_dump"), *args, "--format=custom", "--no-owner", "--no-privileges"]
    cmd += ["--file", str(path), db_name]
    try:
        _run(cmd, env)
    except BackupError:
        path.unlink(missing_ok=True)  # never leave a half-written dump behind
        raise
    if path.stat().st_size == 0:
        path.unlink()
        raise BackupError("pg_dump produced an empty file.")
    return path


def restore_database(dump_path: Path) -> None:
    """Replace the current database contents with the dump (in one transaction)."""
    connections.close_all()  # pg_restore needs the tables free of our own locks
    args, env = _connection_args()
    db_name = connections["default"].settings_dict["NAME"]
    cmd = [_tool("pg_restore"), *args, "--dbname", db_name, "--clean", "--if-exists"]
    cmd += ["--no-owner", "--no-privileges", "--single-transaction", str(dump_path)]
    _run(cmd, env)


def prune_local(directory: Path, keep: int) -> list[Path]:
    dumps = sorted(directory.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"), reverse=True)
    removed = dumps[keep:]
    for path in removed:
        path.unlink(missing_ok=True)
    return removed
