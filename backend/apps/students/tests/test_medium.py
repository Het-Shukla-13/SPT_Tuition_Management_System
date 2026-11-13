"""Medium of instruction on the student profile."""

import pytest

from apps.students.tests.test_students import (
    ADMIN_URL,
    admin,
    client_for,
    payload,
    refs,
)

__all__ = ["admin", "refs"]  # pytest fixtures, imported for use below


@pytest.mark.django_db
class TestMedium:
    def test_admission_keeps_medium_and_it_can_be_edited_and_filtered(
        self, admin, refs
    ):
        client = client_for(admin)
        response = client.post(
            ADMIN_URL, payload(refs, medium="GUJARATI"), format="json"
        )
        assert response.status_code == 201
        student = response.json()["data"]["student"]
        assert student["medium"] == "GUJARATI"

        patched = client.patch(
            f"{ADMIN_URL}{student['id']}/", {"medium": "ENGLISH"}, format="json"
        )
        assert patched.json()["data"]["medium"] == "ENGLISH"
        assert len(client.get(ADMIN_URL, {"medium": "ENGLISH"}).json()["data"]) == 1
        assert client.get(ADMIN_URL, {"medium": "HINDI"}).json()["data"] == []

    def test_medium_is_optional_and_validated(self, admin, refs):
        client = client_for(admin)
        assert client.post(ADMIN_URL, payload(refs), format="json").status_code == 201
        bad = client.post(ADMIN_URL, payload(refs, medium="FRENCH"), format="json")
        assert bad.status_code == 400
        assert "medium" in bad.json()["errors"]
