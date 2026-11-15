"""A student can have several guardians (contacts on file, not logins)."""

import pytest

from apps.students.models import StudentGuardian
from apps.students.tests.test_students import (
    ADMIN_URL,
    admin,
    admit,
    client_for,
    payload,
    refs,
)

__all__ = ["admin", "refs"]  # pytest fixtures, imported for use below

MOTHER = {"name": "Kavita Shah", "relation": "Mother", "phone": "98765 43210"}
FATHER = {
    "name": "Rohan Shah",
    "relation": "Father",
    "phone": "91234 56780",
    "email": "rohan@example.com",
}


@pytest.mark.django_db
class TestGuardians:
    def test_admission_saves_several_in_order(self, admin, refs):
        response = client_for(admin).post(
            ADMIN_URL, payload(refs, guardians=[MOTHER, FATHER]), format="json"
        )
        assert response.status_code == 201, response.json()
        guardians = response.json()["data"]["student"]["guardians"]
        assert [(g["name"], g["relation"], g["phone"]) for g in guardians] == [
            ("Kavita Shah", "Mother", "+919876543210"),
            ("Rohan Shah", "Father", "+919123456780"),
        ]
        assert guardians[1]["email"] == "rohan@example.com"

    def test_editing_replaces_the_list_and_is_audited(self, admin, refs):
        from apps.audit.models import AuditLog

        student = admit(admin, refs, guardians=[MOTHER])
        client = client_for(admin)
        response = client.patch(
            f"{ADMIN_URL}{student.pk}/", {"guardians": [FATHER, MOTHER]}, format="json"
        )
        assert [g["name"] for g in response.json()["data"]["guardians"]] == [
            "Rohan Shah",
            "Kavita Shah",
        ]
        assert StudentGuardian.objects.filter(student=student).count() == 2
        log = AuditLog.objects.filter(action="STUDENT_UPDATED").last()
        assert "guardians" in log.changes

        # Leaving guardians out of an edit keeps them.
        client.patch(f"{ADMIN_URL}{student.pk}/", {"address": "Bopal"}, format="json")
        assert StudentGuardian.objects.filter(student=student).count() == 2

    def test_at_most_four_each_needs_a_name_and_a_valid_phone(self, admin, refs):
        client = client_for(admin)
        five = client.post(
            ADMIN_URL, payload(refs, guardians=[MOTHER] * 5), format="json"
        )
        assert five.status_code == 400
        nameless = client.post(
            ADMIN_URL,
            payload(refs, guardians=[{"phone": "98765 43210"}]),
            format="json",
        )
        assert nameless.status_code == 400
        bad_phone = client.post(
            ADMIN_URL,
            payload(refs, guardians=[{"name": "X", "phone": "12"}]),
            format="json",
        )
        assert bad_phone.status_code == 400

    def test_search_finds_any_guardian(self, admin, refs):
        admit(admin, refs, guardians=[MOTHER, FATHER], new_logins=[])
        client = client_for(admin)
        for term in ["Rohan", "91234", "rohan@example"]:
            data = client.get(ADMIN_URL, {"search": term}).json()["data"]
            assert [s["first_name"] for s in data] == ["Aarav"], term

    def test_duplicate_check_uses_every_guardian_phone(self, admin, refs):
        admit(admin, refs, guardians=[MOTHER, FATHER], new_logins=[])
        again = client_for(admin).post(
            ADMIN_URL,
            payload(
                refs,
                date_of_birth="2015-01-01",  # different birth date...
                guardians=[
                    {"name": "Rohan Shah", "phone": "91234 56780"}
                ],  # ...same father
                new_logins=[],
            ),
            format="json",
        )
        assert again.json()["error_code"] == "POSSIBLE_DUPLICATE_STUDENT"

    def test_fees_search_by_second_guardians_phone(self, admin, refs):
        admit(
            admin, refs, guardians=[MOTHER, FATHER], new_logins=[], agreed_fee="20000"
        )
        response = client_for(admin).get(
            "/api/v1/admin/fees/accounts/", {"search": "91234"}
        )
        assert len(response.json()["data"]) == 1
