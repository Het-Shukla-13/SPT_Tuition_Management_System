"""Extra fees for optional subjects (e.g. Gujarati, Hindi), per fee structure.

Each is its own line on the student's account, so parents see what they pay for.
"""

import datetime
from decimal import Decimal

import pytest

from apps.academics.models import AcademicYear, Subject
from apps.fees.models import FeeStructure, FeeStructureAddOn, LedgerEntry
from apps.fees.tests.test_fees import ACC, STRUCT, admin, admit, client_for, refs

__all__ = ["admin", "refs"]  # pytest fixtures, imported for use below


def guj():
    return Subject.objects.get(code="GUJ")


def hin():
    return Subject.objects.get(code="HIN")


def structure(refs, total=20000, add_ons=None, year=None):
    s = FeeStructure.objects.create(
        academic_year=year or AcademicYear.current(refs["cbse"]),
        standard=refs["tenth"],
        total_fee=total,
    )
    for subject, amount in (add_ons or {}).items():
        FeeStructureAddOn.objects.create(structure=s, subject=subject, amount=amount)
    return s


def totals(admin, account):
    return client_for(admin).get(f"{ACC}{account.pk}/").json()["data"]


@pytest.mark.django_db
class TestStructureAddOns:
    def test_structure_saves_and_replaces_its_add_ons(self, admin, refs):
        client = client_for(admin)
        year = AcademicYear.current(refs["cbse"])
        created = client.post(
            STRUCT,
            {
                "academic_year": year.pk,
                "standard": refs["tenth"].pk,
                "total_fee": "20000",
                "add_ons": [
                    {"subject": guj().pk, "amount": "2000"},
                    {"subject": hin().pk, "amount": "1500"},
                ],
            },
            format="json",
        )
        assert created.status_code == 201, created.json()
        data = created.json()["data"]
        assert {a["subject_name"]: a["amount"] for a in data["add_ons"]} == {
            "Gujarati": "2000.00",
            "Hindi": "1500.00",
        }

        updated = client.patch(
            f"{STRUCT}{data['id']}/",
            {"add_ons": [{"subject": guj().pk, "amount": "2500"}]},
            format="json",
        ).json()["data"]
        assert [(a["subject_name"], a["amount"]) for a in updated["add_ons"]] == [
            ("Gujarati", "2500.00")
        ]
        # Leaving add_ons out keeps them.
        kept = client.patch(
            f"{STRUCT}{data['id']}/", {"total_fee": "21000"}, format="json"
        ).json()["data"]
        assert len(kept["add_ons"]) == 1

    def test_rejects_the_same_subject_twice_and_zero_amounts(self, admin, refs):
        client = client_for(admin)
        body = {
            "academic_year": AcademicYear.current(refs["cbse"]).pk,
            "standard": refs["tenth"].pk,
            "total_fee": "20000",
        }
        twice = client.post(
            STRUCT,
            {
                **body,
                "add_ons": [
                    {"subject": guj().pk, "amount": "2000"},
                    {"subject": guj().pk, "amount": "1000"},
                ],
            },
            format="json",
        )
        assert twice.status_code == 400
        zero = client.post(
            STRUCT,
            {**body, "add_ons": [{"subject": guj().pk, "amount": "0"}]},
            format="json",
        )
        assert zero.status_code == 400

    def test_filter_current_year(self, admin, refs):
        structure(refs)
        found = client_for(admin).get(STRUCT, {"academic_year__is_current": "true"})
        assert len(found.json()["data"]) == 1


@pytest.mark.django_db
class TestAdmissionCharges:
    def test_charges_the_structure_extras_only_for_subjects_taken(self, admin, refs):
        structure(refs, add_ons={guj(): 2000, hin(): 1500})
        _, account = admit(admin, refs, subjects=[refs["maths"].pk, guj().pk])

        lines = LedgerEntry.objects.filter(account=account, entry_type="CHARGE")
        assert {(e.subject.code if e.subject else "base", e.amount) for e in lines} == {
            ("GUJ", Decimal("2000")),
            ("base", Decimal("20000")),
        }
        assert account.agreed_fee == Decimal("20000")  # base fee stays separate
        assert Decimal(totals(admin, account)["total"]) == Decimal("22000")

    def test_form_can_change_or_drop_the_extra(self, admin, refs):
        structure(refs, add_ons={guj(): 2000})
        _, account = admit(
            admin,
            refs,
            subjects=[refs["maths"].pk, guj().pk],
            subject_fees=[{"subject": guj().pk, "amount": "1000"}],
        )
        assert Decimal(totals(admin, account)["total"]) == Decimal("21000")

        _, waived = admit(
            admin,
            refs,
            name="Riya",
            phone="9000000099",
            subjects=[refs["maths"].pk, guj().pk],
            subject_fees=[],
        )
        assert Decimal(totals(admin, waived)["total"]) == Decimal("20000")

    def test_extra_only_for_a_subject_they_take(self, admin, refs):
        structure(refs, add_ons={guj(): 2000})
        response = client_for(admin).post(
            "/api/v1/admin/students/",
            {
                "first_name": "Kabir",
                "last_name": "Shah",
                "board": refs["cbse"].pk,
                "standard": refs["tenth"].pk,
                "school": refs["school"].pk,
                "subjects": [refs["maths"].pk],
                "subject_fees": [{"subject": guj().pk, "amount": "2000"}],
                "confirm_duplicate": True,
            },
            format="json",
        )
        assert response.status_code == 400
        assert "subject_fees" in response.json()["errors"]

    def test_history_names_the_subject(self, admin, refs):
        structure(refs, add_ons={guj(): 2000})
        _, account = admit(admin, refs, subjects=[refs["maths"].pk, guj().pk])
        entries = totals(admin, account)["entries"]
        extra = next(e for e in entries if e["subject"])
        assert extra["subject_name"] == "Gujarati"
        assert extra["remarks"] == "Gujarati (optional subject)"


@pytest.mark.django_db
class TestMidYearChanges:
    def test_add_then_take_off_a_subject_fee(self, admin, refs):
        structure(refs)
        _, account = admit(admin, refs)
        client = client_for(admin)
        url = f"{ACC}{account.pk}/subject-fees/"

        added = client.post(
            url, {"subject": hin().pk, "action": "ADD", "amount": "1500"}, format="json"
        )
        assert added.status_code == 201
        assert Decimal(added.json()["data"]["total"]) == Decimal("21500")

        again = client.post(
            url, {"subject": hin().pk, "action": "ADD", "amount": "1500"}, format="json"
        )
        assert again.json()["error_code"] == "SUBJECT_FEE_ALREADY_CHARGED"

        removed = client.post(
            url,
            {"subject": hin().pk, "action": "REMOVE", "reason": "Dropped Hindi"},
            format="json",
        )
        assert removed.status_code == 201
        assert Decimal(removed.json()["data"]["total"]) == Decimal("20000")
        line = LedgerEntry.objects.filter(account=account, subject=hin()).last()
        assert line.entry_type == "ADJUSTMENT" and line.amount == Decimal("-1500")

    def test_partial_removal_and_limits(self, admin, refs):
        structure(refs, add_ons={guj(): 2000})
        _, account = admit(admin, refs, subjects=[refs["maths"].pk, guj().pk])
        client = client_for(admin)
        url = f"{ACC}{account.pk}/subject-fees/"

        too_much = client.post(
            url,
            {"subject": guj().pk, "action": "REMOVE", "amount": "5000"},
            format="json",
        )
        assert too_much.status_code == 400
        half = client.post(
            url,
            {"subject": guj().pk, "action": "REMOVE", "amount": "1000"},
            format="json",
        )
        assert Decimal(half.json()["data"]["total"]) == Decimal("21000")
        nothing = client.post(
            url, {"subject": hin().pk, "action": "REMOVE"}, format="json"
        )
        assert nothing.json()["error_code"] == "SUBJECT_FEE_NOT_CHARGED"

    def test_add_needs_an_amount(self, admin, refs):
        structure(refs)
        _, account = admit(admin, refs)
        response = client_for(admin).post(
            f"{ACC}{account.pk}/subject-fees/",
            {"subject": guj().pk, "action": "ADD"},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
def test_rollover_charges_the_new_years_extras(admin, refs):
    structure(refs, add_ons={guj(): 2000})
    student, _ = admit(
        admin,
        refs,
        subjects=[refs["maths"].pk, guj().pk],
        standard="ninth",
        agreed_fee="20000",
    )
    next_year = AcademicYear.objects.create(
        board=refs["cbse"],
        name="2027-28",
        start_date=datetime.date(2027, 4, 1),
        end_date=datetime.date(2028, 3, 31),
    )
    structure(refs, total=27000, add_ons={guj(): 2500}, year=next_year)

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
    extra = LedgerEntry.objects.get(account=account, subject=guj())
    assert extra.entry_type == "CHARGE" and extra.amount == Decimal("2500")
