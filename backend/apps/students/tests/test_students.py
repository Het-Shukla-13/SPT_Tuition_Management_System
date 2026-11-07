"""Students: admission, siblings & shared access, history, status, subjects, portal, IDOR."""

import pytest
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Board, School, Standard, Subject
from apps.accounts.models import User, UserSession
from apps.accounts.services.sms import LocmemSMSBackend
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.students.models import (
    StudentAcademicHistory,
    StudentAccess,
    StudentProfile,
    StudentSubject,
)

ADMIN_URL = "/api/v1/admin/students/"
PORTAL_URL = "/api/v1/portal/students/"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def refs(db):
    return {
        "cbse": Board.objects.get(code="CBSE"),
        "gseb": Board.objects.get(code="GSEB"),
        "ninth": Standard.objects.get(level=9),
        "tenth": Standard.objects.get(level=10),
        "school": School.objects.create(name="St. Xavier's", city="Ahmedabad"),
        "school2": School.objects.create(name="DPS", city="Ahmedabad"),
        "maths": Subject.objects.get(code="MATH"),
        "sci": Subject.objects.get(code="SCI"),
        "eng": Subject.objects.get(code="ENG"),
    }


def payload(refs, **overrides):
    return {
        "first_name": "Aarav",
        "last_name": "Shah",
        "date_of_birth": "2011-05-10",
        "guardian_name": "Priya Shah",
        "guardian_phone": "98765 43210",
        "board": refs["cbse"].pk,
        "standard": refs["tenth"].pk,
        "school": refs["school"].pk,
        "subjects": [refs["maths"].pk, refs["sci"].pk],
        "new_logins": [
            {"first_name": "Priya", "last_name": "Shah", "phone": "9876543210"}
        ],
        **overrides,
    }


def admit(admin, refs, **overrides):
    response = client_for(admin).post(
        ADMIN_URL, payload(refs, **overrides), format="json"
    )
    assert response.status_code == 201, response.json()
    return StudentProfile.objects.get(pk=response.json()["data"]["student"]["id"])


# ─── admission ───────────────────────────────────────────────
@pytest.mark.django_db
class TestAdmission:
    def test_admit_creates_profile_subjects_history_and_parent_login(
        self, admin, refs, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = client_for(admin).post(ADMIN_URL, payload(refs), format="json")

        assert response.status_code == 201
        data = response.json()["data"]
        year = timezone.localdate().year
        assert data["student"]["admission_number"] == f"SPT-{year}-0001"
        assert {s["subject"]["code"] for s in data["student"]["subjects"]} == {
            "MATH",
            "SCI",
        }
        assert data["student"]["guardian_phone"] == "+919876543210"  # normalised

        student = StudentProfile.objects.get()
        history = StudentAcademicHistory.objects.get(student=student)
        assert history.reason == "ADMISSION" and history.ended_on is None
        assert history.academic_year == AcademicYear.current()

        parent = User.objects.get(phone="+919876543210")
        assert parent.role == User.Role.PORTAL and parent.invited_by == admin
        assert StudentAccess.objects.filter(user=parent, student=student).exists()
        assert LocmemSMSBackend.outbox[-1]["to"] == "+919876543210"  # invite sent
        assert AuditLog.objects.filter(action="STUDENT_ADMITTED").exists()

    def test_admission_numbers_increase(self, admin, refs):
        first = admit(admin, refs)
        second = admit(
            admin, refs, first_name="Riya", new_logins=[], date_of_birth="2014-01-01"
        )
        assert first.admission_number.endswith("-0001")
        assert second.admission_number.endswith("-0002")

    def test_student_without_any_login_is_allowed(self, admin, refs):
        student = admit(admin, refs, new_logins=[])
        assert not student.access_links.exists()

    @pytest.mark.parametrize(
        "missing",
        ["first_name", "last_name", "board", "standard", "school", "subjects"],
    )
    def test_required_fields(self, admin, refs, missing):
        body = payload(refs)
        del body[missing]
        response = client_for(admin).post(ADMIN_URL, body, format="json")
        assert response.status_code == 400
        assert missing in response.json()["errors"]

    def test_subjects_cannot_be_empty_or_repeated(self, admin, refs):
        client = client_for(admin)
        assert (
            client.post(
                ADMIN_URL, payload(refs, subjects=[]), format="json"
            ).status_code
            == 400
        )
        twice = payload(refs, subjects=[refs["maths"].pk, refs["maths"].pk])
        assert client.post(ADMIN_URL, twice, format="json").status_code == 400

    def test_possible_duplicate_warns_then_confirm_admits(self, admin, refs):
        admit(admin, refs, new_logins=[])
        client = client_for(admin)

        warned = client.post(ADMIN_URL, payload(refs, new_logins=[]), format="json")
        assert warned.status_code == 409
        assert warned.json()["error_code"] == "POSSIBLE_DUPLICATE_STUDENT"
        assert len(warned.json()["errors"]["possible_duplicates"]) == 1

        confirmed = client.post(
            ADMIN_URL,
            payload(refs, new_logins=[], confirm_duplicate=True),
            format="json",
        )
        assert confirmed.status_code == 201
        assert StudentProfile.objects.count() == 2

    def test_same_name_different_birth_date_is_not_a_duplicate(self, admin, refs):
        admit(admin, refs, new_logins=[], guardian_phone="")
        admit(admin, refs, new_logins=[], guardian_phone="", date_of_birth="2012-12-12")
        assert StudentProfile.objects.count() == 2

    def test_cannot_link_a_non_portal_login(self, admin, refs):
        teacher = User.objects.create_user(
            email="t@example.com", role=User.Role.TEACHER
        )
        response = client_for(admin).post(
            ADMIN_URL,
            payload(refs, new_logins=[], link_user_ids=[teacher.pk]),
            format="json",
        )
        assert response.json()["error_code"] == "NOT_A_PORTAL_LOGIN"
        assert not StudentProfile.objects.exists()  # whole admission rolled back

    def test_taken_phone_for_new_login_rolls_back_everything(self, admin, refs):
        User.objects.create_user(phone="+919876543210")
        response = client_for(admin).post(ADMIN_URL, payload(refs), format="json")
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONTACT_IN_USE"
        assert not StudentProfile.objects.exists()
        assert not StudentAcademicHistory.objects.exists()

    def test_needs_a_current_academic_year(self, admin, refs):
        AcademicYear.objects.update(is_current=False)
        response = client_for(admin).post(ADMIN_URL, payload(refs), format="json")
        assert response.json()["error_code"] == "NO_CURRENT_ACADEMIC_YEAR"

    def test_inactive_standard_rejected(self, admin, refs):
        Standard.objects.filter(pk=refs["tenth"].pk).update(is_active=False)
        response = client_for(admin).post(ADMIN_URL, payload(refs), format="json")
        assert response.json()["error_code"] == "INACTIVE_REFERENCE"

    @pytest.mark.parametrize("role", [User.Role.TEACHER, User.Role.PORTAL])
    def test_only_admins_admit(self, refs, role):
        actor = User.objects.create_user(email="x@example.com", role=role)
        response = client_for(actor).post(ADMIN_URL, payload(refs), format="json")
        assert response.status_code == 403
        assert not StudentProfile.objects.exists()


# ─── admin management ────────────────────────────────────────
@pytest.mark.django_db
class TestAdminManagement:
    def test_list_search_filter_and_paginate(self, admin, refs):
        admit(admin, refs)
        admit(
            admin,
            refs,
            first_name="Riya",
            standard=refs["ninth"].pk,
            new_logins=[],
            date_of_birth="2014-01-01",
        )
        client = client_for(admin)

        everyone = client.get(ADMIN_URL).json()
        assert everyone["meta"]["total_count"] == 2

        by_name = client.get(ADMIN_URL, {"search": "riya"}).json()["data"]
        assert [s["first_name"] for s in by_name] == ["Riya"]

        by_parent_login = client.get(ADMIN_URL, {"search": "9876543210"}).json()["data"]
        assert {s["first_name"] for s in by_parent_login} == {
            "Aarav",
            "Riya",
        }  # guardian phone too

        ninth = client.get(ADMIN_URL, {"standard": refs["ninth"].pk}).json()["data"]
        assert [s["first_name"] for s in ninth] == ["Riya"]

    def test_detail_shows_subjects_and_logins(self, admin, refs):
        student = admit(admin, refs)
        data = client_for(admin).get(f"{ADMIN_URL}{student.pk}/").json()["data"]
        assert len(data["subjects"]) == 2
        assert data["logins"][0]["phone"] == "+919876543210"
        assert data["logins"][0]["invite_accepted"] is False

    def test_edit_personal_details(self, admin, refs):
        student = admit(admin, refs)
        response = client_for(admin).patch(
            f"{ADMIN_URL}{student.pk}/",
            {"address": "Satellite, Ahmedabad"},
            format="json",
        )
        assert response.json()["data"]["address"] == "Satellite, Ahmedabad"
        assert AuditLog.objects.filter(action="STUDENT_UPDATED").exists()

    def test_change_standard_keeps_history(self, admin, refs):
        student = admit(admin, refs, standard=refs["ninth"].pk)
        client = client_for(admin)

        response = client.post(
            f"{ADMIN_URL}{student.pk}/academic/",
            {"standard": refs["tenth"].pk, "reason": "PROMOTION"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["data"]["standard"]["name"] == "10th"
        history = client.get(f"{ADMIN_URL}{student.pk}/history/").json()["data"]
        assert [(h["standard"], h["reason"]) for h in history] == [
            ("10th", "PROMOTION"),
            ("9th", "ADMISSION"),
        ]
        assert history[1]["ended_on"] is not None and history[0]["ended_on"] is None

    def test_academic_change_requires_a_change(self, admin, refs):
        student = admit(admin, refs)
        response = client_for(admin).post(
            f"{ADMIN_URL}{student.pk}/academic/",
            {"standard": refs["tenth"].pk, "reason": "CORRECTION"},
            format="json",
        )
        assert response.json()["error_code"] == "NOTHING_CHANGED"

    def test_leaving_keeps_records(self, admin, refs):
        student = admit(admin, refs)
        client = client_for(admin)

        left = client.post(
            f"{ADMIN_URL}{student.pk}/status/", {"status": "LEFT"}, format="json"
        )
        assert left.json()["data"]["status"] == "LEFT"
        assert left.json()["data"]["left_on"] is not None
        assert StudentAcademicHistory.objects.filter(student=student).exists()
        assert StudentSubject.objects.filter(student=student).count() == 2

        back = client.post(
            f"{ADMIN_URL}{student.pk}/status/", {"status": "ACTIVE"}, format="json"
        )
        assert back.json()["data"]["left_on"] is None

    def test_replace_subjects_keeps_dropped_as_history(self, admin, refs):
        student = admit(admin, refs)
        response = client_for(admin).put(
            f"{ADMIN_URL}{student.pk}/subjects/",
            {"subjects": [refs["maths"].pk, refs["eng"].pk]},
            format="json",
        )
        assert {s["subject"]["code"] for s in response.json()["data"]["subjects"]} == {
            "MATH",
            "ENG",
        }
        science = StudentSubject.objects.get(student=student, subject=refs["sci"])
        assert science.ended_on is not None  # dropped, not deleted

    def test_reference_data_in_use_cannot_be_deleted(self, admin, refs):
        admit(admin, refs)
        with pytest.raises(ProtectedError):
            refs["tenth"].delete()


# ─── access links & portal ───────────────────────────────────
@pytest.mark.django_db
class TestAccessAndPortal:
    def test_sibling_linked_to_same_parent_shows_both(self, admin, refs):
        aarav = admit(admin, refs)
        parent = User.objects.get(phone="+919876543210")
        riya = admit(
            admin,
            refs,
            first_name="Riya",
            new_logins=[],
            link_user_ids=[parent.pk],
            date_of_birth="2014-01-01",
        )

        students = client_for(parent).get(PORTAL_URL).json()["data"]
        assert {s["id"] for s in students} == {aarav.pk, riya.pk}

    def test_second_parent_and_kids_own_login(self, admin, refs):
        aarav = admit(admin, refs)
        riya = admit(
            admin, refs, first_name="Riya", new_logins=[], date_of_birth="2014-01-01"
        )
        client = client_for(admin)
        client.post(
            f"{ADMIN_URL}{aarav.pk}/access/",
            {
                "new_login": {
                    "first_name": "Raj",
                    "last_name": "Shah",
                    "phone": "9000000001",
                }
            },
            format="json",
        )
        client.post(
            f"{ADMIN_URL}{aarav.pk}/access/",
            {
                "new_login": {
                    "first_name": "Aarav",
                    "last_name": "Shah",
                    "phone": "9000000002",
                }
            },
            format="json",
        )

        dad = User.objects.get(phone="+919000000001")
        kid = User.objects.get(phone="+919000000002")
        assert [s["id"] for s in client_for(dad).get(PORTAL_URL).json()["data"]] == [
            aarav.pk
        ]
        kid_client = client_for(kid)
        assert [s["id"] for s in kid_client.get(PORTAL_URL).json()["data"]] == [
            aarav.pk
        ]
        assert (
            kid_client.get(f"{PORTAL_URL}{riya.pk}/").status_code == 404
        )  # not his sister's

    def test_other_students_are_invisible(self, admin, refs):
        admit(admin, refs)
        stranger_child = admit(
            admin,
            refs,
            first_name="Kabir",
            guardian_phone="9111111111",
            date_of_birth="2011-01-01",
            new_logins=[{"first_name": "X", "last_name": "Y", "phone": "9111111111"}],
        )
        parent = User.objects.get(phone="+919876543210")
        response = client_for(parent).get(f"{PORTAL_URL}{stranger_child.pk}/")
        assert response.status_code == 404  # IDOR: changing the id reveals nothing

    def test_grant_existing_login_twice_conflicts(self, admin, refs):
        student = admit(admin, refs)
        parent = User.objects.get(phone="+919876543210")
        response = client_for(admin).post(
            f"{ADMIN_URL}{student.pk}/access/", {"user_id": parent.pk}, format="json"
        )
        assert response.json()["error_code"] == "ACCESS_ALREADY_GRANTED"

    def test_revoke_access_takes_effect_and_keeps_history(self, admin, refs):
        student = admit(admin, refs)
        parent = User.objects.get(phone="+919876543210")
        parent_client = client_for(parent)
        parent_client.post(f"{PORTAL_URL}{student.pk}/select/")

        response = client_for(admin).delete(
            f"{ADMIN_URL}{student.pk}/access/{parent.pk}/"
        )

        assert response.status_code == 200
        assert parent_client.get(PORTAL_URL).json()["data"] == []
        assert parent_client.get(f"{PORTAL_URL}{student.pk}/").status_code == 404
        assert (
            StudentAccess.objects.get(user=parent, student=student).revoked_at
            is not None
        )
        assert not UserSession.objects.filter(
            user=parent, selected_student__isnull=False
        ).exists()
        assert parent.is_active  # the login itself remains

    def test_selection_is_per_device(self, admin, refs):
        aarav = admit(admin, refs)
        parent = User.objects.get(phone="+919876543210")
        riya = admit(
            admin,
            refs,
            first_name="Riya",
            new_logins=[],
            link_user_ids=[parent.pk],
            date_of_birth="2014-01-01",
        )
        phone, laptop = client_for(parent), client_for(parent)

        phone.post(f"{PORTAL_URL}{riya.pk}/select/")
        laptop.post(f"{PORTAL_URL}{aarav.pk}/select/")

        def selected(client):
            data = client.get(PORTAL_URL).json()["data"]
            return [s["id"] for s in data if s["is_selected"]]

        assert selected(phone) == [riya.pk]
        assert selected(laptop) == [aarav.pk]

    def test_cannot_select_an_unlinked_student(self, admin, refs):
        student = admit(admin, refs, new_logins=[])
        outsider = User.objects.create_user(phone="+919222222222")
        assert (
            client_for(outsider).post(f"{PORTAL_URL}{student.pk}/select/").status_code
            == 404
        )

    def test_left_student_still_listed_with_status(self, admin, refs):
        student = admit(admin, refs)
        client_for(admin).post(
            f"{ADMIN_URL}{student.pk}/status/", {"status": "LEFT"}, format="json"
        )
        parent = User.objects.get(phone="+919876543210")
        assert client_for(parent).get(PORTAL_URL).json()["data"][0]["status"] == "LEFT"

    def test_login_with_no_students_sees_nothing(self):
        lonely = User.objects.create_user(phone="+919333333333")
        assert client_for(lonely).get(PORTAL_URL).json()["data"] == []

    def test_roles_stay_in_their_lane(self, admin, refs):
        student = admit(admin, refs)
        parent = User.objects.get(phone="+919876543210")
        teacher = User.objects.create_user(
            email="t@example.com", role=User.Role.TEACHER
        )
        assert client_for(admin).get(PORTAL_URL).status_code == 403
        assert client_for(teacher).get(PORTAL_URL).status_code == 403
        assert client_for(parent).get(ADMIN_URL).status_code == 403
        assert client_for(parent).get(f"{ADMIN_URL}{student.pk}/").status_code == 403
