# Phase 4: Fees, per-board academic years, year-end rollover (design)

Status: **agreed (owner, 2026-11-08)**, ready to build. Spec: part 6 (sections 8.1-8.7), 9.5,
edge-case register (Fees). Builds on Phase 2 (students, history) and Phase 3 (academic year usage).

## Owner decisions
1. **Academic years are per board**, dates entered manually by the admin every year (they change
   year to year). Each board has its own current year.
2. **Fees are due at the end of the student's board's academic year.** Alerts: "term ends within
   30 days with dues" and "term ended with dues" (overdue). Automatic SMS/email reminders need a
   daily scheduled job, switched on at deployment (Phase 8).
3. **Overpayment becomes credit**, applied automatically to later dues (e.g. next year's fee).
4. **PDF receipt** per payment, for staff and the student's linked logins.
5. **Methods:** CASH, UPI, BANK_TRANSFER, CHEQUE, OTHER (note required).
6. **Unpaid dues and credit carry forward** into the next year's account at rollover.
7. **After the last standard taught (10th)**, rollover marks students **COMPLETED** (new status,
   separate from LEFT).

## A. Per-board academic years (changes Phase 2)
- `AcademicYear.board` (FK). Unique (board, name). **One current year per board** (partial unique).
- Existing data: the seeded global 2026-27 is copied to one year per board (same dates, editable).
- Student history rows, tests/notes and fee accounts use the **student's board's** year.
- Admission uses the current year of the chosen board (`NO_CURRENT_ACADEMIC_YEAR` per board).

## B. Fees (`fees` app)
| Model (table) | Purpose |
|---|---|
| `FeeStructure` (`fee_structures`) | Standard fee per board + standard + academic year; description, `is_active`. Suggestion for new admissions only; editing it never changes existing accounts. |
| `StudentFeeAccount` (`student_fee_accounts`) | One per student per academic year: `agreed_fee`, `opening_balance` (carried dues, + or credit, -), status cache. Totals are always computed from ledger entries. |
| `LedgerEntry` (`fee_ledger_entries`) | Append-only money record: type `CHARGE` (agreed fee) / `ADJUSTMENT` (+/-, reason) / `PAYMENT` / `REVERSAL` (of a payment, reason) / `REFUND` / `CARRY_FORWARD`. Amount (Decimal 12,2), date, method, reference, remarks, `visible_to_student`, recorded_by, `idempotency_key` (unique), `reverses` (FK to the reversed entry, one reversal max). |
| `Receipt` | Generated PDF per payment (number `RCPT-<year>-NNNNN`), rendered on demand. |

**Balance:** `due = opening_balance + charges + adjustments - payments + reversals + refunds`.
`pending = max(due, 0)`, `credit = max(-due, 0)`. Status: PAID (due = 0), PARTIAL, PENDING (nothing paid),
CREDIT (due < 0), plus OVERDUE (due > 0 after the year's end date) / ENDING_SOON (within 30 days).

**Integrity (spec 8.6):** entries are never edited or deleted; corrections are reversals/adjustments;
every write locks the account row (`select_for_update`) inside a transaction (concurrent admins);
`Idempotency-Key` header makes a repeated "Save" a no-op returning the original entry; money is
`Decimal`; all writes audited.

## C. Admission + rollover
- Admission form gains `agreed_fee` (pre-filled from `FeeStructure`, editable) and optional
  `opening_balance` + reason (dues from before the app). Creates the fee account in the same transaction.
- **Rollover** (admin, per board): `POST /admin/rollover/preview` {board, to_year} → every ACTIVE
  student of that board with a suggested action: PROMOTE (+1 standard), REPEAT, LEAVE, COMPLETE
  (last standard). Admin edits actions and agreed fees, then `POST /admin/rollover/apply`:
  per student, one transaction: history row closed + new row, standard/status updated, new fee
  account with carried-forward dues/credit. Per-student success/failure report; re-running for a
  student already rolled into that year is refused.

## D. APIs
| Who | Endpoints |
|---|---|
| Admin | `/admin/fee-structures/` CRUD (no delete) |
| Admin | `/admin/fees/accounts/`: list with filters (status incl. overdue/ending soon/credit, pending/paid/total ranges, standard, board, school, academic year, student status, admission date range), search (name, admission no., guardian phone), sort (pending, total, paid, name, standard, last payment) |
| Admin | `/admin/fees/accounts/{id}/`: detail + ledger; `payments/` (POST, Idempotency-Key), `adjustments/`, `refunds/`, `entries/{id}/reverse/`; agreed-fee change = adjustment |
| Admin | `/admin/fees/payments/`: all payments, filters date range / method / amount range / recorded by / reversed |
| Admin, portal | `.../receipts/{entry_id}/` PDF |
| Admin | `/admin/rollover/preview`, `/admin/rollover/apply` |
| Portal | `/portal/students/{id}/fees/`: accounts by year with totals, status, due date, payment history, student-visible remarks, receipts. Read-only. |
| Teacher | no access to fees |

## E. Validation
Amount > 0 with ≤ 2 decimals; payment date not in the future; method from the list (OTHER needs a
note); reason required for adjustments/reversals/refunds; reversal once per payment and only of a
payment; refund ≤ net paid; agreed fee ≥ 0; one account per (student, academic year); fee structure
unique per (board, standard, year).
