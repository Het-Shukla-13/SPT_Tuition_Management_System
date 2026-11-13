"""Owner accounts can't be changed by anyone else in the app, not even another owner.

Changes to an owner are made by that owner (their own account page) or directly
in the database.
"""

import pytest

from apps.accounts.models import User
from apps.accounts.tests.test_admin_users import ME_URL, client_for, url


@pytest.fixture
def owner(db):
    return User.objects.create_superuser(email="owner@example.com", password="x" * 12)


@pytest.fixture
def second_owner(db):
    return User.objects.create_superuser(email="father@example.com", password="y" * 12)


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


def _attempts(target):
    """Every way one login can change another from the app."""
    return [
        ("patch", url(target), {"first_name": "Changed"}),
        ("post", url(target, "deactivate"), {}),
        ("post", url(target, "activate"), {}),
        ("post", url(target, "role"), {"role": "TEACHER"}),
        ("post", url(target, "resend-invite"), {}),
        (
            "post",
            url(target, "contact"),
            {"channel": "EMAIL", "identifier": "x@example.com"},
        ),
    ]


@pytest.mark.django_db
class TestOwnerProtection:
    def test_another_owner_cannot_change_an_owner(self, owner, second_owner):
        client = client_for(owner)
        for method, path, data in _attempts(second_owner):
            response = getattr(client, method)(path, data, format="json")
            assert response.status_code == 403, (method, path, response.json())
            assert response.json()["error_code"] == "OWNER_PROTECTED", path

        second_owner.refresh_from_db()
        assert second_owner.is_active
        assert second_owner.role == User.Role.ADMIN
        assert second_owner.first_name != "Changed"
        assert second_owner.email == "father@example.com"

    def test_a_regular_admin_cannot_change_an_owner(self, admin, owner):
        client = client_for(admin)
        for method, path, data in _attempts(owner):
            response = getattr(client, method)(path, data, format="json")
            assert response.status_code == 403, (method, path)

    def test_an_owner_still_edits_their_own_details(self, owner):
        response = client_for(owner).patch(ME_URL, {"first_name": "Het"}, format="json")
        assert response.status_code == 200
        assert response.json()["data"]["first_name"] == "Het"

    def test_an_owner_still_manages_regular_admins(self, owner, admin):
        client = client_for(owner)
        assert (
            client.patch(url(admin), {"first_name": "Meera"}, format="json").status_code
            == 200
        )
        assert (
            client.post(url(admin, "deactivate"), {}, format="json").status_code == 200
        )
