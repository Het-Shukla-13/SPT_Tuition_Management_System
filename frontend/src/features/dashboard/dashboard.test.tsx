import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, http, makeUser, ok, page, renderScreen, setupMockServer } from "@/test/render";

import type { Dashboard } from "./api";
import { DashboardPage } from "./pages/DashboardPage";

const server = setupMockServer();

const FEES: NonNullable<Dashboard["fees"]> = {
  scope: "current academic year of each board",
  accounts: 42,
  students_with_pending_fees: 10,
  students_fully_paid: 32,
  total_outstanding: "85000.00",
  total_collected: "640000.00",
  total_credit: "0.00",
  overdue: 1,
  ending_soon_with_dues: 0,
  recent_payments: [
    {
      id: 2,
      student: "Aarav Shah",
      amount: "5000.00",
      method: "UPI",
      entry_date: "2026-11-02",
      receipt_number: "SPT-R-0009",
      reversed: false,
    },
  ],
};

const BASE: Dashboard = {
  students: {
    active: 42,
    on_hold: 1,
    left: 3,
    completed: 5,
    new_admissions: 4,
    new_admissions_days: 30,
    active_by_standard: [
      { standard__name: "Standard 9", standard__level: 9, count: 12 },
      { standard__name: "Standard 10", standard__level: 10, count: 30 },
    ],
    recent_admissions: [
      {
        id: 7,
        admission_number: "SPT-2026-0012",
        name: "Aarav Shah",
        standard: "Standard 10",
        board: "CBSE",
        admission_date: "2026-11-01",
      },
    ],
  },
  learning: { upcoming_tests_7_days: 3, tests_to_grade: 2, recent_tests: [], recent_notes: [] },
};

beforeEach(() => {
  server.use(
    http.get(`${API}/academics/boards/`, () =>
      ok([{ id: 1, code: "CBSE", name: "Central Board" }], page(1)),
    ),
  );
});

describe("DashboardPage", () => {
  it("shows an admin the numbers, fees and what needs attention", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/staff/dashboard/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok({ ...BASE, fees: FEES });
      }),
      http.get(`${API}/admin/enquiries/`, () => ok([], page(3))),
    );
    const { user, search } = renderScreen(<DashboardPage />, { path: "/staff" });

    const attention = await screen.findByLabelText("Needs attention");
    expect(attention).toHaveTextContent("2 tests are over and waiting for marks");
    expect(attention).toHaveTextContent("1 student has overdue fees");
    await waitFor(() =>
      expect(attention).toHaveTextContent("3 new admission enquiries to follow up"),
    );

    expect(screen.getByRole("link", { name: /Fees outstanding/ })).toHaveTextContent("₹85,000");
    expect(screen.getByRole("table", { name: "Active students by standard" })).toHaveTextContent(
      "Standard 1030",
    );
    expect(screen.getByText(/SPT-R-0009/)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Board"), "1");
    await waitFor(() => expect(seen.at(-1)?.get("board")).toBe("1"));
    expect(search()).toContain("board=1");
  });

  it("never shows a teacher fees or enquiries", async () => {
    let askedForEnquiries = false;
    server.use(
      http.get(`${API}/staff/dashboard/`, () => ok(BASE)),
      http.get(`${API}/admin/enquiries/`, () => {
        askedForEnquiries = true;
        return ok([], page(0));
      }),
    );
    renderScreen(<DashboardPage />, {
      path: "/staff",
      me: makeUser({ role: "TEACHER", first_name: "Meera" }),
    });

    expect(await screen.findByText("Tests waiting for marks")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hello, Meera" })).toBeInTheDocument();
    expect(screen.queryByText(/Fees outstanding/)).not.toBeInTheDocument();
    expect(screen.queryByText("Recent admissions")).not.toBeInTheDocument();
    expect(askedForEnquiries).toBe(false);
  });
});
