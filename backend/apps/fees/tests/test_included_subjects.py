"""Fee structures cover their included subjects; optional subjects are extras.

A subject is either included (covered by the standard fee) or optional, never
both. The agreed-fee line on a new account names the subjects it covers.
"""

import datetime
from decimal import Decimal

import pytest

from apps.academics.models import AcademicYear, Subject
from apps.fees.models import FeeStructure, LedgerEntry
from apps.fees.services import standard_fee_remarks
from apps.fees.tests.test_fees import STRUCT, admin, admit, client_for, refs
from apps.fees.tests.test_subject_fees import guj, hin, structure

__all__ = ["admin", "refs"]  # pytest fixtures, imported for use below


def subject(code):
    return Subject.objects.get(code=code)


def body(refs, **extra):
    return {
        "academic_year": AcademicYear.current(refs["cbse"]).pk,
        "standard": refs["tenth"].pk,
        "total_fee": "20000",
        **extra,
    }


@pytest.mark.django_db
class TestMainSubjects:
    def test_seeded_main_subjects(self):
        main = set(Subject.objects.filter(is_main=True).values_list("code", flat=True))
        assert main == {"ENG", "MATH", "SCI", "SST"}

    def test_subjects_api_reads_and_writes_is_main(self, admin):
        client = client_for(admin)
        data = client.get(f"/api/v1/academics/subjects/{guj().pk}/").json()["data"]
        assert data["is_main"] is False
        updated = client.patch(
            f"/api/v1/academics/subjects/{guj().pk}/", {"is_main": True}, format="json"
        )
        assert updated.status_code == 200, updated.json()
        assert guj().is_main is True


@pytest.mark.django_db
class TestStructureIncludedSubjects:
    def test_saves_and_returns_included_subjects(self, admin, refs):
        client = client_for(admin)
        created = client.post(
            STRUCT,
            body(
                refs,
                included_subjects=[refs["maths"].pk, subject("SCI").pk],
                add_ons=[{"subject": guj().pk, "amount": "2000"}],
            ),
            format="json",
        )
        assert created.status_code == 201, created.json()
        data = created.json()["data"]
        assert sorted(data["included_subjects"]) == sorted(
            [refs["maths"].pk, subject("SCI").pk]
        )
        assert data["included_subject_names"] == ["Mathematics", "Science"]

        # Sending the list replaces it; leaving it out keeps it.
        replaced = client.patch(
            f"{STRUCT}{data['id']}/",
            {"included_subjects": [subject("ENG").pk]},
            format="json",
        ).json()["data"]
        assert replaced["included_subject_names"] == ["English"]
        kept = client.patch(
            f"{STRUCT}{data['id']}/", {"total_fee": "21000"}, format="json"
        ).json()["data"]
        assert kept["included_subject_names"] == ["English"]
        assert len(kept["add_ons"]) == 1

    def test_defaults_to_none_when_not_sent(self, admin, refs):
        created = client_for(admin).post(STRUCT, body(refs), format="json")
        assert created.status_code == 201
        assert created.json()["data"]["included_subjects"] == []

    def test_a_subject_cant_be_included_and_optional(self, admin, refs):
        response = client_for(admin).post(
            STRUCT,
            body(
                refs,
                included_subjects=[refs["maths"].pk, guj().pk],
                add_ons=[{"subject": guj().pk, "amount": "2000"}],
            ),
            format="json",
        )
        assert response.status_code == 400
        errors = response.json()["errors"]["included_subjects"]
        assert "Gujarati can't be both included and optional" in errors[0]

    def test_overlap_checked_against_the_saved_list(self, admin, refs):
        s = structure(refs, add_ons={guj(): 2000})
        s.included_subjects.set([refs["maths"]])
        client = client_for(admin)
        adds_included = client.patch(
            f"{STRUCT}{s.pk}/", {"included_subjects": [guj().pk]}, format="json"
        )
        assert adds_included.status_code == 400
        adds_optional = client.patch(
            f"{STRUCT}{s.pk}/",
            {"add_ons": [{"subject": refs["maths"].pk, "amount": "500"}]},
            format="json",
        )
        assert adds_optional.status_code == 400
        # Moving it across in one request is fine.
        moved = client.patch(
            f"{STRUCT}{s.pk}/",
            {
                "included_subjects": [],
                "add_ons": [{"subject": refs["maths"].pk, "amount": "500"}],
            },
            format="json",
        )
        assert moved.status_code == 200, moved.json()

    def test_standard_fee_cant_be_negative(self, admin, refs):
        response = client_for(admin).post(
            STRUCT, body(refs, total_fee="-1"), format="json"
        )
        assert response.status_code == 400
        assert "total_fee" in response.json()["errors"]

    def test_included_subjects_on_the_model(self, refs):
        s = FeeStructure.objects.create(
            academic_year=AcademicYear.current(refs["cbse"]),
            standard=refs["tenth"],
            total_fee=20000,
        )
        s.included_subjects.set(Subject.objects.filter(is_main=True))
        assert set(s.included_subjects.values_list("code", flat=True)) == {
            "ENG",
            "MATH",
            "SCI",
            "SST",
        }


@pytest.mark.django_db
class TestStandardFeeLine:
    def test_remarks_name_the_covered_subjects(self, refs):
        year = AcademicYear.current(refs["cbse"])
        text = standard_fee_remarks(
            year,
            [refs["maths"], subject("SCI"), guj()],
            [(guj(), Decimal("2000"))],
        )
        assert text == f"Standard fee for {year} (Mathematics, Science)"
        assert standard_fee_remarks(year) == f"Standard fee for {year}"
        # A waived optional fee (0) means the standard fee covers it.
        waived = standard_fee_remarks(year, [guj()], [(guj(), Decimal("0"))])
        assert waived == f"Standard fee for {year} (Gujarati)"

    def test_admission_line_names_its_subjects(self, admin, refs):
        structure(refs, add_ons={guj(): 2000})
        _, account = admit(
            admin,
            refs,
            subjects=[refs["maths"].pk, subject("SCI").pk, guj().pk],
        )
        line = LedgerEntry.objects.get(
            account=account, entry_type="CHARGE", subject__isnull=True
        )
        year = AcademicYear.current(refs["cbse"])
        assert line.remarks == f"Standard fee for {year} (Mathematics, Science)"

    def test_a_subject_made_optional_for_one_student(self, admin, refs):
        # Science is charged as its own line for this student only.
        s = structure(refs)
        s.included_subjects.set([refs["maths"], subject("SCI")])
        _, account = admit(
            admin,
            refs,
            subjects=[refs["maths"].pk, subject("SCI").pk],
            agreed_fee="17000",
            subject_fees=[{"subject": subject("SCI").pk, "amount": "3000"}],
        )
        base = LedgerEntry.objects.get(
            account=account, entry_type="CHARGE", subject__isnull=True
        )
        assert base.amount == Decimal("17000")
        assert base.remarks.endswith("(Mathematics)")
        sci = LedgerEntry.objects.get(account=account, subject=subject("SCI"))
        assert sci.amount == Decimal("3000")
        s.refresh_from_db()
        assert s.total_fee == Decimal("20000")  # the structure never changes

    def test_rollover_line_names_its_subjects(self, admin, refs):
        structure(refs, add_ons={hin(): 1500})
        student, _ = admit(
            admin,
            refs,
            standard="ninth",
            agreed_fee="20000",
            subjects=[refs["maths"].pk, hin().pk],
        )
        next_year = AcademicYear.objects.create(
            board=refs["cbse"],
            name="2027-28",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
        )
        structure(refs, total=27000, add_ons={hin(): 1500}, year=next_year)
        result = (
            client_for(admin)
            .post(
                "/api/v1/admin/rollover/apply/",
                {
                    "board": refs["cbse"].pk,
                    "to_year": next_year.pk,
                    "items": [{"student_id": student.pk, "action": "PROMOTE"}],
                },
                format="json",
            )
            .json()["data"]
        )
        assert result["failed"] == []
        account = student.fee_accounts.get(academic_year=next_year)
        line = LedgerEntry.objects.get(
            account=account, entry_type="CHARGE", subject__isnull=True
        )
        assert line.remarks == f"Standard fee for {next_year} (Mathematics)"
