"""Fees: admission accounts, payments (idempotent), corrections, credit, filters, receipts, portal, rollover."""

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Board, School, Standard, Subject
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.fees.models import FeeStructure, LedgerEntry, StudentFeeAccount
from apps.students.models import StudentAcademicHistory, StudentProfile

ADMIT = "/api/v1/admin/students/"
ACC = "/api/v1/admin/fees/accounts/"
PAYMENTS = "/api/v1/admin/fees/payments/"
STRUCT = "/api/v1/admin/fee-structures/"


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def refs(db):
    return {
        "cbse": Board.objects.get(code="CBSE"),
        "ninth": Standard.objects.get(level=9),
        "tenth": Standard.objects.get(level=10),
        "school": School.objects.create(name="DPS", city="Ahmedabad"),
        "maths": Subject.objects.get(code="MATH"),
    }


def admit(admin, refs, name="Aarav", standard="tenth", phone="9876543210", **extra):
    body = {
        "first_name": name,
        "last_name": "Shah",
        "date_of_birth": "2011-01-01",
        "board": refs["cbse"].pk,
        "standard": refs[standard].pk,
        "school": refs["school"].pk,
        "subjects": [refs["maths"].pk],
        "guardian_phone": phone,
        "confirm_duplicate": True,
        "new_logins": [{"first_name": "Parent", "last_name": name, "phone": phone}],
        **extra,
    }
    response = client_for(admin).post(ADMIT, body, format="json")
    assert response.status_code == 201, response.json()
    student = StudentProfile.objects.get(pk=response.json()["data"]["student"]["id"])
    return student, StudentFeeAccount.objects.get(student=student)


def pay(admin, account, amount="10000", key=None, **extra):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client_for(admin).post(
        f"{ACC}{account.pk}/payments/",
        {"amount": amount, "method": "CASH", **extra},
        format="json",
        **headers,
    )


def detail(admin, account):
    return client_for(admin).get(f"{ACC}{account.pk}/").json()["data"]


# ─── admission → account ─────────────────────────────────────
@pytest.mark.django_db
class TestAccounts:
    def test_admission_creates_account_with_agreed_fee(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        data = detail(admin, account)
        assert (data["total"], data["paid"], data["pending"], data["status"]) == (
            "22000.00",
            "0.00",
            "22000.00",
            "PENDING",
        )
        assert data["entries"][0]["entry_type"] == "CHARGE"
        assert data["due_date"] == str(AcademicYear.current(refs["cbse"]).end_date)

    def test_fee_structure_used_when_no_agreed_fee(self, admin, refs):
        FeeStructure.objects.create(
            academic_year=AcademicYear.current(refs["cbse"]),
            standard=refs["tenth"],
            total_fee=25000,
        )
        _, account = admit(admin, refs)
        assert account.agreed_fee == Decimal("25000")

    def test_fee_required_without_structure(self, admin, refs):
        body = {
            "first_name": "X",
            "last_name": "Y",
            "board": refs["cbse"].pk,
            "standard": refs["tenth"].pk,
            "school": refs["school"].pk,
            "subjects": [refs["maths"].pk],
        }
        response = client_for(admin).post(ADMIT, body, format="json")
        assert response.json()["error_code"] == "FEE_REQUIRED"
        assert not StudentProfile.objects.exists()

    def test_opening_balance_needs_reason_and_counts(self, admin, refs):
        response = client_for(admin).post(
            ADMIT,
            {
                "first_name": "X",
                "last_name": "Y",
                "board": refs["cbse"].pk,
                "standard": refs["tenth"].pk,
                "school": refs["school"].pk,
                "subjects": [refs["maths"].pk],
                "agreed_fee": "20000",
                "opening_balance": "3000",
            },
            format="json",
        )
        assert "opening_balance_reason" in response.json()["errors"]
        _, account = admit(
            admin,
            refs,
            agreed_fee="20000",
            opening_balance="3000",
            opening_balance_reason="Dues from 2025-26 (before the app)",
        )
        assert detail(admin, account)["total"] == "23000.00"

    def test_changing_fee_structure_never_touches_existing_accounts(self, admin, refs):
        structure = FeeStructure.objects.create(
            academic_year=AcademicYear.current(refs["cbse"]),
            standard=refs["tenth"],
            total_fee=25000,
        )
        _, account = admit(admin, refs)
        client_for(admin).patch(
            f"{STRUCT}{structure.pk}/", {"total_fee": "30000"}, format="json"
        )
        assert detail(admin, account)["total"] == "25000.00"


# ─── payments & integrity ────────────────────────────────────
@pytest.mark.django_db
class TestPayments:
    def test_partial_payment_and_receipt_number(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        response = pay(admin, account, "10000", reference="", remarks="June instalment")
        assert response.status_code == 201
        assert (
            response.json()["data"]["payment"]["receipt_number"]
            == f"RCPT-{timezone.localdate().year}-00001"
        )
        data = response.json()["data"]["account"]
        assert (data["paid"], data["pending"], data["status"]) == (
            "10000.00",
            "12000.00",
            "PARTIAL",
        )
        assert AuditLog.objects.filter(action="FEE_PAYMENT_RECORDED").exists()

    def test_double_submit_is_recorded_once(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        first = pay(admin, account, key="save-click-123")
        second = pay(admin, account, key="save-click-123")
        assert first.status_code == 201 and second.status_code == 200
        assert LedgerEntry.objects.filter(entry_type="PAYMENT").count() == 1
        assert detail(admin, account)["paid"] == "10000.00"

    def test_same_key_on_another_account_conflicts(self, admin, refs):
        _, a1 = admit(admin, refs, agreed_fee="22000")
        _, a2 = admit(admin, refs, name="Riya", phone="9000000001", agreed_fee="22000")
        pay(admin, a1, key="k-1")
        assert pay(admin, a2, key="k-1").json()["error_code"] == "IDEMPOTENCY_CONFLICT"

    @pytest.mark.parametrize(
        "amount,extra,code",
        [
            ("0", {}, "INVALID_AMOUNT"),
            ("-5", {}, "INVALID_AMOUNT"),
            ("100", {"entry_date": "2999-01-01"}, "FUTURE_DATE"),
            ("100", {"method": "OTHER"}, "NOTE_REQUIRED"),
        ],
    )
    def test_payment_validation(self, admin, refs, amount, extra, code):
        _, account = admit(admin, refs, agreed_fee="22000")
        response = pay(admin, account, amount, **extra)
        assert response.json()["error_code"] == code
        assert not LedgerEntry.objects.filter(entry_type="PAYMENT").exists()

    def test_overpayment_becomes_credit(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        pay(admin, account, "25000")
        data = detail(admin, account)
        assert (data["status"], data["credit"], data["pending"]) == (
            "CREDIT",
            "3000.00",
            "0.00",
        )

    def test_full_payment_paid(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        pay(admin, account, "22000")
        assert detail(admin, account)["status"] == "PAID"


# ─── corrections ─────────────────────────────────────────────
@pytest.mark.django_db
class TestCorrections:
    def test_reverse_wrong_payment_keeps_history(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        wrong = pay(admin, account, "15000").json()["data"]["payment"]["id"]
        client = client_for(admin)

        response = client.post(
            f"/api/v1/admin/fees/entries/{wrong}/reverse/",
            {"reason": "Typed 15000 instead of 10000"},
            format="json",
        )
        assert response.status_code == 201
        pay(admin, account, "10000")
        data = detail(admin, account)
        assert data["paid"] == "10000.00"
        assert [e["entry_type"] for e in data["entries"]] == [
            "CHARGE",
            "PAYMENT",
            "REVERSAL",
            "PAYMENT",
        ]
        assert data["entries"][1]["reversed"] is True

        again = client.post(
            f"/api/v1/admin/fees/entries/{wrong}/reverse/",
            {"reason": "x"},
            format="json",
        )
        assert again.json()["error_code"] == "ALREADY_REVERSED"

    def test_only_payments_can_be_reversed(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        charge = LedgerEntry.objects.get(entry_type="CHARGE")
        response = client_for(admin).post(
            f"/api/v1/admin/fees/entries/{charge.pk}/reverse/",
            {"reason": "x"},
            format="json",
        )
        assert response.json()["error_code"] == "NOT_A_PAYMENT"

    def test_agreed_fee_change_is_an_auditable_adjustment(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="25000")
        pay(admin, account, "10000")
        response = client_for(admin).post(
            f"{ACC}{account.pk}/agreed-fee/",
            {"agreed_fee": "22000", "reason": "Sibling discount"},
            format="json",
        )
        data = response.json()["data"]
        assert (data["agreed_fee"], data["total"], data["pending"]) == (
            "22000.00",
            "22000.00",
            "12000.00",
        )
        assert (
            data["entries"][-1]["entry_type"] == "ADJUSTMENT"
            and data["entries"][-1]["amount"] == "-3000.00"
        )

    def test_concession_needs_reason(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        client = client_for(admin)
        assert (
            client.post(
                f"{ACC}{account.pk}/adjustments/",
                {"amount": "-2000", "reason": ""},
                format="json",
            ).status_code
            == 400
        )
        ok = client.post(
            f"{ACC}{account.pk}/adjustments/",
            {"amount": "-2000", "reason": "Merit concession"},
            format="json",
        )
        assert ok.json()["data"]["pending"] == "20000.00"

    def test_refund_limited_to_paid(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        pay(admin, account, "10000")
        client = client_for(admin)
        too_much = client.post(
            f"{ACC}{account.pk}/refunds/",
            {"amount": "12000", "method": "UPI", "reason": "Left"},
            format="json",
        )
        assert too_much.json()["error_code"] == "REFUND_TOO_LARGE"
        ok = client.post(
            f"{ACC}{account.pk}/refunds/",
            {"amount": "4000", "method": "UPI", "reason": "Left mid-year"},
            format="json",
        )
        assert ok.json()["data"]["paid"] == "6000.00"


# ─── fees table filters & payments list ──────────────────────
@pytest.mark.django_db
class TestFiltersAndLists:
    def _three(self, admin, refs):
        _, paid = admit(
            admin, refs, name="Asha", phone="9000000001", agreed_fee="20000"
        )
        _, partial = admit(
            admin, refs, name="Bina", phone="9000000002", agreed_fee="20000"
        )
        _, pending = admit(
            admin,
            refs,
            name="Chet",
            phone="9000000003",
            agreed_fee="30000",
            standard="ninth",
        )
        pay(admin, paid, "20000")
        pay(admin, partial, "5000", method="UPI")
        return paid, partial, pending

    def test_status_range_sort_and_search(self, admin, refs):
        self._three(admin, refs)
        client = client_for(admin)

        def names(**params):
            rows = client.get(ACC, params).json()["data"]
            return [r["student_name"] for r in rows]

        assert names(status="PAID") == ["Asha Shah"]
        assert names(status="PARTIAL") == ["Bina Shah"]
        assert names(status="PENDING") == ["Chet Shah"]
        assert names(pending_min="10000", pending_max="20000") == ["Bina Shah"]
        assert names(ordering="-pending") == ["Chet Shah", "Bina Shah", "Asha Shah"]
        assert names(search="bina") == ["Bina Shah"]
        assert names(student__standard=refs["ninth"].pk) == ["Chet Shah"]

    def test_overdue_and_ending_soon(self, admin, refs):
        _, partial, _ = self._three(admin, refs)
        year = AcademicYear.current(refs["cbse"])
        client = client_for(admin)
        year.end_date = timezone.localdate() + datetime.timedelta(days=10)
        year.save()
        assert (
            len(client.get(ACC, {"status": "ENDING_SOON"}).json()["data"]) == 2
        )  # dues > 0
        year.end_date = timezone.localdate() - datetime.timedelta(days=1)
        year.start_date = year.end_date - datetime.timedelta(days=300)
        year.save()
        overdue = client.get(ACC, {"status": "OVERDUE"}).json()["data"]
        assert {r["student_name"] for r in overdue} == {"Bina Shah", "Chet Shah"}

    def test_payments_list_filters(self, admin, refs):
        self._three(admin, refs)
        client = client_for(admin)
        assert len(client.get(PAYMENTS).json()["data"]) == 2
        assert [
            p["amount"] for p in client.get(PAYMENTS, {"method": "UPI"}).json()["data"]
        ] == ["5000.00"]
        assert len(client.get(PAYMENTS, {"amount__gte": "10000"}).json()["data"]) == 1

    def test_teachers_and_portal_have_no_fee_access(self, admin, refs):
        _, account = admit(admin, refs, agreed_fee="22000")
        teacher = User.objects.create_user(
            email="t@example.com", role=User.Role.TEACHER
        )
        parent = User.objects.get(phone="+919876543210")
        for user in (teacher, parent):
            assert client_for(user).get(ACC).status_code == 403
            assert pay(user, account).status_code == 403


# ─── receipts & portal ───────────────────────────────────────
@pytest.mark.django_db
class TestReceiptsAndPortal:
    def test_receipt_pdf_for_admin_and_own_parent_only(self, admin, refs):
        student, account = admit(admin, refs, agreed_fee="22000")
        other, other_account = admit(
            admin, refs, name="Kabir", phone="9111111111", agreed_fee="22000"
        )
        entry_id = pay(admin, account).json()["data"]["payment"]["id"]
        other_entry = pay(admin, other_account).json()["data"]["payment"]["id"]

        admin_pdf = client_for(admin).get(f"{PAYMENTS}{entry_id}/receipt/")
        assert admin_pdf[
            "Content-Type"
        ] == "application/pdf" and admin_pdf.content.startswith(b"%PDF")

        parent = client_for(User.objects.get(phone="+919876543210"))
        base = f"/api/v1/portal/students/{student.pk}/fees/receipts/"
        assert parent.get(f"{base}{entry_id}/").status_code == 200
        assert parent.get(f"{base}{other_entry}/").status_code == 404

    def test_portal_sees_fees_read_only_with_hidden_remarks(self, admin, refs):
        student, account = admit(admin, refs, agreed_fee="22000")
        pay(admin, account, "5000", remarks="Paid by uncle", visible_to_student=False)
        parent = client_for(User.objects.get(phone="+919876543210"))
        data = parent.get(f"/api/v1/portal/students/{student.pk}/fees/").json()["data"]
        assert data[0]["pending"] == "17000.00" and data[0]["status"] == "PARTIAL"
        payment = [e for e in data[0]["entries"] if e["entry_type"] == "PAYMENT"][0]
        assert payment["remarks"] == ""


# ─── year-end rollover ───────────────────────────────────────
@pytest.mark.django_db
class TestRollover:
    def _next_year(self, refs, make_structure=True):
        year = AcademicYear.objects.create(
            board=refs["cbse"],
            name="2027-28",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
        )
        if make_structure:
            FeeStructure.objects.create(
                academic_year=year, standard=refs["tenth"], total_fee=27000
            )
        return year

    def test_preview_suggests_promote_and_complete(self, admin, refs):
        nine, nine_acc = admit(
            admin,
            refs,
            name="Nina",
            phone="9000000011",
            standard="ninth",
            agreed_fee="20000",
        )
        admit(admin, refs, name="Tara", phone="9000000012", agreed_fee="25000")
        pay(admin, nine_acc, "15000")
        year = self._next_year(refs)

        rows = (
            client_for(admin)
            .post(
                "/api/v1/admin/rollover/preview/",
                {"board": refs["cbse"].pk, "to_year": year.pk},
                format="json",
            )
            .json()["data"]
        )
        by_name = {r["name"]: r for r in rows}
        assert by_name["Nina Shah"]["suggested_action"] == "PROMOTE"
        assert by_name["Nina Shah"]["to_standard"] == "10th"
        assert by_name["Nina Shah"]["suggested_agreed_fee"] == Decimal("27000")
        assert by_name["Nina Shah"]["balance_to_carry"] == Decimal("5000")
        assert by_name["Tara Shah"]["suggested_action"] == "COMPLETE"

    def test_apply_promotes_carries_dues_and_completes(self, admin, refs):
        nine, nine_acc = admit(
            admin,
            refs,
            name="Nina",
            phone="9000000011",
            standard="ninth",
            agreed_fee="20000",
        )
        ten, _ = admit(admin, refs, name="Tara", phone="9000000012", agreed_fee="25000")
        pay(admin, nine_acc, "15000")
        year = self._next_year(refs)
        client = client_for(admin)

        result = client.post(
            "/api/v1/admin/rollover/apply/",
            {
                "board": refs["cbse"].pk,
                "to_year": year.pk,
                "items": [
                    {"student_id": nine.pk, "action": "PROMOTE"},
                    {"student_id": ten.pk, "action": "COMPLETE"},
                ],
            },
            format="json",
        ).json()["data"]

        assert len(result["done"]) == 2 and result["failed"] == []
        nine.refresh_from_db()
        ten.refresh_from_db()
        assert nine.standard == refs["tenth"] and ten.status == "COMPLETED"
        assert AcademicYear.current(refs["cbse"]) == year
        new_acc = StudentFeeAccount.objects.get(student=nine, academic_year=year)
        assert detail(admin, new_acc)["total"] == "32000.00"  # 27000 + 5000 carried
        assert detail(admin, nine_acc)["status"] == "CARRIED_FORWARD"
        assert StudentAcademicHistory.objects.filter(student=nine).count() == 2

        again = client.post(
            "/api/v1/admin/rollover/apply/",
            {
                "board": refs["cbse"].pk,
                "to_year": year.pk,
                "items": [{"student_id": nine.pk, "action": "REPEAT"}],
            },
            format="json",
        ).json()["data"]
        assert again["failed"][0]["reason"] == "ALREADY_ROLLED_OVER"

    def test_credit_carries_and_fee_required(self, admin, refs):
        nine, acc = admit(
            admin,
            refs,
            name="Nina",
            phone="9000000011",
            standard="ninth",
            agreed_fee="20000",
        )
        other, _ = admit(
            admin,
            refs,
            name="Om",
            phone="9000000013",
            standard="ninth",
            agreed_fee="20000",
        )
        pay(admin, acc, "21000")  # 1000 credit
        year = self._next_year(refs, make_structure=False)
        result = (
            client_for(admin)
            .post(
                "/api/v1/admin/rollover/apply/",
                {
                    "board": refs["cbse"].pk,
                    "to_year": year.pk,
                    "items": [
                        {
                            "student_id": nine.pk,
                            "action": "REPEAT",
                            "agreed_fee": "21000",
                        },
                        {"student_id": other.pk, "action": "PROMOTE"},
                    ],
                },
                format="json",
            )
            .json()["data"]
        )
        new_acc = StudentFeeAccount.objects.get(student=nine, academic_year=year)
        assert detail(admin, new_acc)["total"] == "20000.00"  # 21000 - 1000 credit
        assert result["failed"] == [
            {
                "student_id": other.pk,
                "reason": "FEE_REQUIRED",
                "message": result["failed"][0]["message"],
            }
        ]

    def test_year_of_another_board_rejected(self, admin, refs):
        gseb_year = AcademicYear.current(Board.objects.get(code="GSEB"))
        response = client_for(admin).post(
            "/api/v1/admin/rollover/preview/",
            {"board": refs["cbse"].pk, "to_year": gseb_year.pk},
            format="json",
        )
        assert response.json()["error_code"] == "WRONG_BOARD_YEAR"
