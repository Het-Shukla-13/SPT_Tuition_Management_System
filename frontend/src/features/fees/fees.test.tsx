import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { LedgerEntry } from "@/lib/api/types";
import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { withRunningBalance } from "./api";
import { FeeAccountPage } from "./pages/FeeAccountPage";
import { FeesPage } from "./pages/FeesPage";

const server = setupMockServer();

const REF = {
  boards: [{ id: 1, code: "CBSE", name: "Central Board", is_active: true }],
  standards: [{ id: 10, name: "Standard 10", level: 10, is_active: true }],
  "academic-years": [
    { id: 4, board: 1, board_code: "CBSE", name: "2026-27", is_current: false, is_active: true },
  ],
};

const entry = (over: Partial<LedgerEntry>): LedgerEntry =>
  ({
    id: 1,
    entry_type: "CHARGE",
    amount: "0.00",
    entry_date: "2026-06-01",
    method: null,
    reference: "",
    remarks: "",
    visible_to_student: true,
    receipt_number: null,
    reverses: null,
    reversed: false,
    recorded_by: 1,
    recorded_by_name: "Owner",
    created_at: "2026-06-01T10:00:00+05:30",
    ...over,
  }) as LedgerEntry;

// Agreed 20,000 → paid 5,000 → paid 3,000 (later reversed).
const ENTRIES = [
  entry({ id: 1, entry_type: "CHARGE", amount: "20000.00" }),
  entry({
    id: 2,
    entry_type: "PAYMENT",
    amount: "5000.00",
    entry_date: "2026-06-10",
    method: "CASH",
    receipt_number: "SPT-R-0001",
  }),
  entry({
    id: 3,
    entry_type: "PAYMENT",
    amount: "3000.00",
    entry_date: "2026-06-20",
    method: "UPI",
    receipt_number: "SPT-R-0002",
    reversed: true,
  }),
  entry({
    id: 4,
    entry_type: "REVERSAL",
    amount: "3000.00",
    entry_date: "2026-06-21",
    reverses: 3,
  }),
];

const ACCOUNT = {
  id: 5,
  student: 7,
  student_name: "Aarav Shah",
  admission_number: "SPT-2026-0012",
  standard: "Standard 10",
  board: "CBSE",
  academic_year: 4,
  academic_year_name: "2026-27",
  due_date: "2027-03-31",
  agreed_fee: "20000.00",
  opening_balance: "0.00",
  total: "20000.00",
  paid: "5000.00",
  pending: "15000.00",
  credit: "0.00",
  status: "PARTIAL",
  is_overdue: false,
  is_ending_soon: false,
  last_payment_date: "2026-06-10",
  opening_balance_reason: "",
  entries: ENTRIES,
};

beforeEach(() => {
  server.use(
    ...Object.entries(REF).map(([key, items]) =>
      http.get(`${API}/academics/${key}/`, () => ok(items, page(items.length))),
    ),
    http.get(`${API}/admin/fees/accounts/5/`, () => ok(ACCOUNT)),
  );
});

describe("withRunningBalance", () => {
  it("orders entries by date and tracks what is still owed", () => {
    const rows = withRunningBalance([...ENTRIES].reverse(), "1000.00");
    expect(rows.map((r) => r.entry.id)).toEqual([1, 2, 3, 4]);
    // 1,000 carried in + 20,000 − 5,000 − 3,000 + 3,000 (reversal)
    expect(rows.map((r) => r.balance)).toEqual([21000, 16000, 13000, 16000]);
  });
});

describe("FeeAccountPage", () => {
  const renderAccount = () =>
    renderScreen(<FeeAccountPage />, {
      path: "/staff/fees/accounts/5",
      route: "/staff/fees/accounts/:id",
    });

  it("shows the history with receipts, and only live payments can be reversed", async () => {
    renderAccount();
    const history = await screen.findByRole("table", { name: "Fee account history" });
    expect(within(history).getByText(/SPT-R-0001/)).toBeInTheDocument();
    expect(within(history).getAllByRole("button", { name: "Receipt" })).toHaveLength(2);
    // The reversed payment can't be reversed again.
    expect(within(history).getAllByRole("button", { name: "Reverse" })).toHaveLength(1);
  });

  it("records a payment with an idempotency key, and a fresh key for the next one", async () => {
    const calls: { key: string | null; body: Record<string, unknown> }[] = [];
    server.use(
      http.post(`${API}/admin/fees/accounts/5/payments/`, async ({ request }) => {
        calls.push({
          key: request.headers.get("Idempotency-Key"),
          body: (await request.json()) as Record<string, unknown>,
        });
        return ok(
          entry({ id: 9, entry_type: "PAYMENT", amount: "2500.00", receipt_number: "SPT-R-0003" }),
        );
      }),
    );
    const { user } = renderAccount();

    await user.type(await screen.findByLabelText("Amount (₹)"), "2500");
    await user.click(screen.getByRole("radio", { name: "UPI" }));
    await user.type(screen.getByLabelText("UPI reference"), "UTR123");
    await user.click(screen.getByRole("button", { name: "Save & create receipt" }));

    expect(await screen.findByText(/receipt SPT-R-0003/)).toBeInTheDocument();
    expect(calls[0]?.body).toMatchObject({ amount: "2500", method: "UPI", reference: "UTR123" });
    expect(calls[0]?.key).toBeTruthy();

    await user.type(screen.getByLabelText("Amount (₹)"), "100");
    await user.click(screen.getByRole("button", { name: "Save & create receipt" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1]?.key).toBeTruthy();
    expect(calls[1]?.key).not.toBe(calls[0]?.key);
  });

  it("asks for a reason before reversing a payment", async () => {
    let body: unknown;
    server.use(
      http.post(`${API}/admin/fees/entries/2/reverse/`, async ({ request }) => {
        body = await request.json();
        return ok(entry({ id: 10, entry_type: "REVERSAL", amount: "5000.00" }));
      }),
    );
    const { user } = renderAccount();
    await user.click(await screen.findByRole("button", { name: "Reverse" }));
    const dialog = await screen.findByRole("dialog", { name: "Reverse this payment?" });

    await user.click(within(dialog).getByRole("button", { name: "Reverse payment" }));
    expect(body).toBeUndefined();

    await user.type(within(dialog).getByLabelText("Reason"), "Cheque bounced");
    await user.click(within(dialog).getByRole("button", { name: "Reverse payment" }));
    await waitFor(() => expect(body).toEqual({ reason: "Cheque bounced" }));
  });
});

describe("FeesPage", () => {
  it("lists accounts by highest pending first and filters by board", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/fees/accounts/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok([ACCOUNT], page(1));
      }),
    );
    const { user, search } = renderScreen(<FeesPage />, { path: "/staff/fees" });

    const link = await screen.findByRole("link", { name: /Aarav Shah/ });
    expect(link).toHaveAttribute("href", "/staff/fees/accounts/5");
    expect(seen[0]?.get("ordering")).toBe("-pending");

    await user.selectOptions(await screen.findByLabelText("Board"), "1");
    await waitFor(() => expect(seen.at(-1)?.get("academic_year__board")).toBe("1"));
    expect(search()).toContain("academic_year__board=1");
  });

  it("previews and applies the year-end rollover, reporting students that failed", async () => {
    let applied: Record<string, unknown> | undefined;
    const preview = [
      {
        student_id: 7,
        admission_number: "SPT-2026-0012",
        name: "Aarav Shah",
        from_standard: "Standard 9",
        suggested_action: "PROMOTE",
        to_standard: "Standard 10",
        suggested_agreed_fee: "22000.00",
        balance_to_carry: "1500.00",
        already_rolled_over: false,
      },
      {
        student_id: 8,
        admission_number: "SPT-2026-0013",
        name: "Riya Patel",
        from_standard: "Standard 9",
        suggested_action: "PROMOTE",
        to_standard: "Standard 10",
        suggested_agreed_fee: "22000.00",
        balance_to_carry: "0.00",
        already_rolled_over: false,
      },
    ];
    server.use(
      http.post(`${API}/admin/rollover/preview/`, () => ok(preview)),
      http.post(`${API}/admin/rollover/apply/`, async ({ request }) => {
        applied = (await request.json()) as Record<string, unknown>;
        return ok({
          done: [{ student_id: 7, action: "PROMOTE" }],
          failed: [
            { student_id: 8, reason: "FEE_REQUIRED", message: "Set a fee for this standard." },
          ],
        });
      }),
    );
    const { user } = renderScreen(<FeesPage />, {
      path: "/staff/fees?tab=rollover",
      route: "/staff/fees",
    });

    const board = await screen.findByLabelText("Board");
    await waitFor(() =>
      expect(within(board).getByRole("option", { name: /CBSE/ })).toBeInTheDocument(),
    );
    await user.selectOptions(board, "1");
    const year = screen.getByLabelText("Move into year");
    await waitFor(() =>
      expect(within(year).getByRole("option", { name: /2026-27/ })).toBeInTheDocument(),
    );
    await user.selectOptions(year, "4");
    await user.click(screen.getByRole("button", { name: "Preview students" }));

    await user.selectOptions(await screen.findByLabelText("What happens to Riya Patel"), "LEAVE");
    const fee = screen.getByLabelText("New yearly fee for Aarav Shah");
    await user.clear(fee);
    await user.type(fee, "21000");
    await user.click(screen.getByRole("button", { name: "Roll over 2 students" }));
    const dialog = await screen.findByRole("dialog", { name: "Roll over students?" });
    expect(dialog).toHaveTextContent("1 promote, 1 left.");
    await user.click(within(dialog).getByRole("button", { name: "Roll over" }));

    await waitFor(() =>
      expect(applied).toEqual({
        board: 1,
        to_year: 4,
        make_current: true,
        items: [
          { student_id: 7, action: "PROMOTE", agreed_fee: "21000" },
          { student_id: 8, action: "LEAVE" },
        ],
      }),
    );
    expect(await screen.findByText(/Set a fee for this standard\./)).toBeInTheDocument();
  });
});
