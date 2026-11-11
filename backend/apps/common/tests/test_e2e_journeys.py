"""
End-to-end journeys (spec Phase 9), driven ONLY through the HTTP API the way
the frontend will: real logins (email OTP + the HttpOnly refresh cookie), no
service calls or database writes after setup. Seeded reference data (boards,
standards, subjects) and the first admin account are the only things created
directly, as in a real installation.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Board, Chapter, Standard, Subject
from apps.accounts.models import User
from apps.accounts.tests.helpers import PASSWORD, last_emailed_code, make_user
from apps.learning.tests.test_learning import body, upload

API = "/api/v1/"
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _browser_like(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.REFRESH_TOKEN_IN_BODY = False  # as in production
    cache.clear()


class Browser:
    """An APIClient that logs in like the real app and keeps the access token in memory."""

    def __init__(self):
        self.client = APIClient()  # holds cookies, like a browser

    def _code(self):
        return last_emailed_code()

    def login(self, email: str, password: str = PASSWORD):
        """Email + password; on a new device, the emailed code too."""
        cache.clear()  # past earlier resend cooldowns
        response = self.post("auth/login/", {"email": email, "password": password})
        data = self.data(response)
        if data["status"] == "OTP_REQUIRED":
            response = self.post(
                "auth/login/verify/",
                {"login_ticket": data["login_ticket"], "code": self._code()},
            )
        return self._finish(response)

    def set_first_password(self, email: str, password: str = PASSWORD):
        """An invited user's first visit: "Set or reset password"."""
        cache.clear()
        self.data(self.post("auth/password/reset/", {"email": email}))
        response = self.post(
            "auth/password/reset/confirm/",
            {"email": email, "code": self._code(), "new_password": password},
        )
        return self._finish(response)

    def _finish(self, response):
        data = self.data(response)
        assert data["status"] == "AUTHENTICATED"
        assert "refresh" not in data  # cookie only
        self._use(data["access"])
        return data["user"]

    def reload(self):
        """A page reload: the in-memory token is gone; the cookie restores the login."""
        self.client.credentials()
        response = self.client.post(
            f"{API}auth/token/refresh/", {}, format="json", **XHR
        )
        if response.status_code == 200:
            self._use(response.json()["data"]["access"])
        return response

    def _use(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def get(self, path, params=None):
        return self.client.get(f"{API}{path}", params or {})

    def post(self, path, data=None, fmt="json", **headers):
        return self.client.post(f"{API}{path}", data or {}, format=fmt, **headers)

    def data(self, response, status=200):
        assert response.status_code == status, response.json()
        return response.json()["data"]


@pytest.fixture
def owner_browser(db):
    make_user("owner@example.com", role=User.Role.ADMIN)
    browser = Browser()
    browser.login("owner@example.com")
    return browser


@pytest.fixture
def refs(db):
    cbse = Board.objects.get(code="CBSE")
    tenth = Standard.objects.get(level=10)
    maths = Subject.objects.get(code="MATH")
    chapter = Chapter.objects.create(
        board=cbse, standard=tenth, subject=maths, number=1, name="Real Numbers"
    )
    return {"cbse": cbse, "tenth": tenth, "maths": maths, "chapter": chapter}


def admit(admin: Browser, school_id, refs, first_name, **extra):
    form = {
        "first_name": first_name,
        "last_name": "Shah",
        "date_of_birth": "2011-05-10" if first_name == "Aarav" else "2014-02-01",
        "guardian_name": "Kavita Shah",
        "guardian_phone": "98765 43210",
        "board": refs["cbse"].pk,
        "standard": refs["tenth"].pk,
        "school": school_id,
        "subjects": [refs["maths"].pk],
        "agreed_fee": "20000",
        **extra,
    }
    response = admin.post("admin/students/", form)
    if response.status_code == 409:  # siblings look alike: the admin confirms
        assert response.json()["error_code"] == "POSSIBLE_DUPLICATE_STUDENT"
        response = admin.post("admin/students/", {**form, "confirm_duplicate": True})
    return admin.data(response, 201)["student"]


@pytest.mark.django_db
def test_parent_journey_two_children_tests_notes_fees(owner_browser, refs):
    admin = owner_browser

    # ── Admin: school, then two siblings sharing one parent login ──
    school = admin.data(
        admin.post("academics/schools/", {"name": "DPS", "city": "Ahmedabad"}), 201
    )
    new_login = {
        "first_name": "Kavita",
        "last_name": "Shah",
        "email": "kavita@example.com",
    }
    aarav = admit(admin, school["id"], refs, "Aarav", new_logins=[new_login])
    parent_id = admin.data(admin.get("admin/users/", {"search": "kavita@"}))[0]["id"]
    riya = admit(admin, school["id"], refs, "Riya", link_user_ids=[parent_id])

    # ── Teacher: test + answer key, assign (test already over), grade; a note ──
    make_user("teacher@example.com", role=User.Role.TEACHER)
    teacher = Browser()
    teacher.login("teacher@example.com")
    paper = teacher.data(
        teacher.post(
            "staff/tests/",
            {
                "title": "Unit test 1",
                "board": refs["cbse"].pk,
                "standard": refs["tenth"].pk,
                "subject": refs["maths"].pk,
                "chapters": [refs["chapter"].pk],
                "max_marks": "25",
                "duration_minutes": "60",
                "file": upload(marker="paper"),
                "answer_key": upload("key.pdf", marker="key"),
            },
            fmt="multipart",
        ),
        201,
    )
    started = (timezone.now() - timedelta(hours=2)).isoformat()
    teacher.data(
        teacher.post(
            f"staff/tests/{paper['id']}/assign/",
            {"student_ids": [aarav["id"]], "test_starts_at": started},
        )
    )
    assignment = teacher.data(
        teacher.get("staff/test-assignments/", {"test_paper": paper["id"]})
    )[0]
    teacher.data(
        teacher.post(
            f"staff/test-assignments/{assignment['id']}/grade/",
            {"marks_obtained": "21.5", "grade_remarks": "Good"},
        )
    )
    note = teacher.data(
        teacher.post(
            "staff/notes/",
            {
                "title": "Real numbers notes",
                "board": refs["cbse"].pk,
                "standard": refs["tenth"].pk,
                "subject": refs["maths"].pk,
                "chapters": [refs["chapter"].pk],
                "file": upload(marker="note"),
            },
            fmt="multipart",
        ),
        201,
    )
    teacher.data(
        teacher.post(
            f"staff/notes/{note['id']}/assign/", {"student_ids": [aarav["id"]]}
        )
    )
    # Teachers can't touch fees or users.
    assert teacher.get("admin/fees/accounts/").status_code == 403

    # ── Admin records a payment (a double-click sends the same key twice) ──
    account = admin.data(admin.get("admin/fees/accounts/", {"search": "Aarav"}))[0]
    for _ in range(2):
        admin.post(
            f"admin/fees/accounts/{account['id']}/payments/",
            {"amount": "5000", "method": "UPI"},
            HTTP_IDEMPOTENCY_KEY="click-1",
        )
    assert len(admin.data(admin.get("admin/fees/payments/"))) == 1

    # ── Parent logs in, reloads the page, picks a child ──
    parent = Browser()
    parent.set_first_password("kavita@example.com")  # invited: no password yet
    assert parent.reload().status_code == 200
    children = parent.data(parent.get("portal/students/"))
    assert {c["first_name"] for c in children} == {"Aarav", "Riya"}
    parent.data(parent.post(f"portal/students/{riya['id']}/select/"))
    assert (
        next(
            c for c in parent.data(parent.get("portal/students/")) if c["is_selected"]
        )["id"]
        == riya["id"]
    )

    # Aarav: graded test, unlocked answer key, the note, fees after the payment.
    base = f"portal/students/{aarav['id']}/"
    [test] = parent.data(parent.get(base + "tests/"))
    assert test["marks_obtained"] == "21.50" and test["answer_key_available"] is True
    key = parent.get(base + f"tests/{test['id']}/download/", {"kind": "ANSWER_KEY"})
    assert key.status_code == 200 and body(key).startswith(b"%PDF")
    assert [n["title"] for n in parent.data(parent.get(base + "notes/"))] == [
        "Real numbers notes"
    ]
    fees = parent.get(base + "fees/")
    assert fees.status_code == 200 and "5000.00" in fees.content.decode()
    assert parent.get(base + "overview/").status_code == 200

    # Riya: nothing assigned yet. A child not linked to this login: 404.
    assert parent.data(parent.get(f"portal/students/{riya['id']}/tests/")) == []
    stranger = admit(
        admin,
        school["id"],
        refs,
        "Dev",
        guardian_phone="98000 00000",
        date_of_birth="2012-01-01",
    )
    assert parent.get(f"portal/students/{stranger['id']}/tests/").status_code == 404
    # Parents can't reach staff or admin areas.
    assert parent.get("staff/tests/").status_code == 403


@pytest.mark.django_db
def test_session_lifecycle_logout_and_deactivation(owner_browser, settings):
    settings.OTP_RESEND_COOLDOWN_SECONDS = 0  # logs the same parent in twice
    admin = owner_browser
    make_user("kavita@example.com")

    # Logout ends the session: a reload can't log back in.
    parent = Browser()
    parent.login("kavita@example.com")
    assert parent.data(parent.post("auth/logout/")) is None
    reload = parent.reload()
    assert reload.status_code == 401

    # Deactivation by the admin: the open session dies at the next refresh.
    parent = Browser()
    user = parent.login("kavita@example.com")
    assert parent.get("auth/me/").status_code == 200
    admin.data(admin.post(f"admin/users/{user['id']}/deactivate/"))
    assert parent.get("auth/me/").status_code == 401
    assert parent.reload().status_code == 401
