import { cleanup, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse } from "msw";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PortalNote, PortalStudent, PortalTest } from "@/lib/api/types";
import { API, http, makeUser, ok, renderScreen, setupMockServer } from "@/test/render";

import { filterNotes } from "./api";
import { StudentGate } from "./components/StudentGate";
import { PortalFeesPage } from "./pages/PortalFeesPage";
import { PortalHomePage } from "./pages/PortalHomePage";
import { PortalTestDetailPage } from "./pages/PortalTestDetailPage";
import { PortalTestsPage } from "./pages/PortalTestsPage";

const server = setupMockServer();
const parent = makeUser({ role: "PORTAL", first_name: "Kavita", last_name: "Shah" });

const student = (over: Partial<PortalStudent>): PortalStudent =>
  ({
    id: 7,
    admission_number: "SPT-2026-0012",
    first_name: "Aarav",
    last_name: "Shah",
    board: { id: 1, code: "CBSE", name: "Central Board" },
    standard: { id: 10, name: "Standard 10", level: 10 },
    school: { id: 3, name: "DPS", city: "Ahmedabad" },
    status: "ACTIVE",
    admission_date: "2026-06-01",
    subjects: [],
    is_selected: false,
    has_photo: false,
    ...over,
  }) as PortalStudent;

const AARAV = student({});
const RIYA = student({ id: 8, first_name: "Riya", admission_number: "SPT-2026-0013" });

const OVERVIEW = {
  student: { id: 7, first_name: "Aarav", last_name: "Shah" },
  upcoming_tests: [
    {
      assignment_id: 31,
      title: "Algebra unit test",
      subject: "Mathematics",
      test_starts_at: "2099-01-10T10:00:00+05:30",
    },
  ],
  recent_results: [
    {
      assignment_id: 30,
      title: "Light chapter test",
      subject: "Science",
      marks_obtained: "18.00",
      max_marks: "25.00",
    },
  ],
  recent_notes: [],
  fees: {
    academic_year: "2026-27",
    due_date: "2027-03-31",
    total: "20000.00",
    paid: "15000.00",
    pending: "5000.00",
    credit: "0.00",
    status: "PARTIAL",
    is_overdue: false,
    pending_all_years: "6500.00",
  },
};

const test_ = (over: Partial<PortalTest>): PortalTest =>
  ({
    id: 31,
    title: "Algebra unit test",
    description: "",
    subject: "Mathematics",
    standard: "Standard 10",
    semester: 1,
    chapters: ["1. Real numbers"],
    assigned_at: "2026-06-01T10:00:00+05:30",
    test_starts_at: "2099-01-10T10:00:00+05:30",
    test_ends_at: "2099-01-10T11:00:00+05:30",
    remarks: "",
    max_marks: "25.00",
    marks_obtained: null,
    grade_remarks: "",
    has_answer_key: true,
    answer_key_available: false,
    ...over,
  }) as PortalTest;

const PAST = test_({
  id: 30,
  title: "Light chapter test",
  subject: "Science",
  test_starts_at: "2026-07-01T10:00:00+05:30",
  test_ends_at: "2026-07-01T11:00:00+05:30",
  marks_obtained: "18.00",
  answer_key_available: true,
});

const withGate = (page: ReactElement) => <StudentGate>{page}</StudentGate>;

beforeEach(() => {
  server.use(http.get(`${API}/portal/students/7/overview/`, () => ok(OVERVIEW)));
});

describe("StudentGate", () => {
  it("asks a parent of several children who's studying, and remembers the choice", async () => {
    let selected: number | undefined;
    server.use(
      http.get(`${API}/portal/students/`, () => ok([AARAV, RIYA])),
      http.post(`${API}/portal/students/:id/select/`, ({ params }) => {
        selected = Number(params.id);
        return ok({ selected_student_id: selected });
      }),
    );
    const { user } = renderScreen(withGate(<PortalHomePage />), { path: "/portal", me: parent });

    expect(await screen.findByRole("heading", { name: "Who's studying?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Aarav Shah/ }));

    expect(await screen.findByRole("heading", { name: "Home" })).toBeInTheDocument();
    expect(selected).toBe(7);
    // With two children, the header offers a switch back to the picker.
    await user.click(screen.getByRole("button", { name: /Switch student/ }));
    expect(await screen.findByRole("heading", { name: "Who's studying?" })).toBeInTheDocument();
  });

  it("goes straight in with a single student, and explains when none is linked", async () => {
    server.use(http.get(`${API}/portal/students/`, () => ok([AARAV])));
    renderScreen(withGate(<PortalHomePage />), { path: "/portal", me: parent });
    expect(await screen.findByRole("heading", { name: "Home" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Switch student/ })).not.toBeInTheDocument();
    cleanup();

    server.use(http.get(`${API}/portal/students/`, () => ok([])));
    renderScreen(withGate(<PortalHomePage />), { path: "/portal", me: parent });
    expect(await screen.findByText("No student is linked to this login yet")).toBeInTheDocument();
  });
});

describe("PortalHomePage", () => {
  it("shows fees due (including earlier years), upcoming tests and results", async () => {
    server.use(http.get(`${API}/portal/students/`, () => ok([AARAV])));
    renderScreen(withGate(<PortalHomePage />), { path: "/portal", me: parent });

    expect(await screen.findByText("₹5,000")).toBeInTheDocument();
    expect(screen.getByText(/from earlier years/)).toHaveTextContent("₹1,500");
    expect(screen.getByRole("link", { name: /Algebra unit test/ })).toHaveAttribute(
      "href",
      "/portal/tests/31",
    );
    expect(screen.getByRole("link", { name: /Light chapter test/ })).toHaveTextContent("18/25");
  });
});

describe("PortalTestsPage", () => {
  it("splits tests into upcoming and past", async () => {
    server.use(
      http.get(`${API}/portal/students/`, () => ok([AARAV])),
      http.get(`${API}/portal/students/7/tests/`, () => ok([PAST, test_({})])),
    );
    const { user, search } = renderScreen(withGate(<PortalTestsPage />), {
      path: "/portal/tests",
      me: parent,
    });

    const upcoming = await screen.findByRole("link", { name: /Algebra unit test/ });
    expect(upcoming).toBeInTheDocument();
    expect(screen.queryByText("Light chapter test")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Past (1)" }));
    expect(await screen.findByRole("link", { name: /Light chapter test/ })).toHaveTextContent(
      "18/25",
    );
    expect(search()).toContain("view=past");
  });
});

describe("PortalTestDetailPage", () => {
  const fakeTab = { location: { href: "" }, close: vi.fn() };
  beforeEach(() => {
    vi.spyOn(window, "open").mockReturnValue(fakeTab as unknown as Window);
    URL.createObjectURL = vi.fn(() => "blob:answer-key");
  });
  afterEach(() => vi.restoreAllMocks());

  const renderTest = (t: PortalTest) => {
    server.use(
      http.get(`${API}/portal/students/`, () => ok([AARAV])),
      http.get(`${API}/portal/students/7/tests/${t.id}/`, () => ok(t)),
    );
    return renderScreen(withGate(<PortalTestDetailPage />), {
      path: `/portal/tests/${t.id}`,
      route: "/portal/tests/:id",
      me: parent,
    });
  };

  it("keeps the answer key locked until the test is over", async () => {
    renderTest(test_({}));
    expect(
      await screen.findByText("The answer key opens after the test ends."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open answer key/ })).not.toBeInTheDocument();
  });

  it("shows marks and opens the answer key afterwards", async () => {
    let kind: string | null = null;
    server.use(
      http.get(`${API}/portal/students/7/tests/30/download/`, ({ request }) => {
        kind = new URL(request.url).searchParams.get("kind");
        return new HttpResponse(new Blob(["%PDF"]), {
          headers: { "Content-Type": "application/pdf" },
        });
      }),
    );
    const { user } = renderTest(PAST);
    expect(await screen.findByText("Marks")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open answer key/ }));
    await waitFor(() => expect(fakeTab.location.href).toBe("blob:answer-key"));
    expect(kind).toBe("ANSWER_KEY");
  });
});

describe("PortalFeesPage", () => {
  it("lists each year's history newest first with receipts for payments", async () => {
    server.use(
      http.get(`${API}/portal/students/`, () => ok([AARAV])),
      http.get(`${API}/portal/students/7/fees/`, () =>
        ok([
          {
            id: 5,
            academic_year_name: "2026-27",
            due_date: "2027-03-31",
            agreed_fee: "20000.00",
            opening_balance: "0.00",
            total: "20000.00",
            paid: "15000.00",
            pending: "5000.00",
            credit: "0.00",
            status: "PARTIAL",
            is_overdue: true,
            is_ending_soon: false,
            last_payment_date: "2026-08-01",
            entries: [
              {
                id: 1,
                entry_type: "CHARGE",
                amount: "20000.00",
                entry_date: "2026-06-01",
                method: "",
                reference: "",
                receipt_number: null,
                remarks: "",
              },
              {
                id: 2,
                entry_type: "PAYMENT",
                amount: "15000.00",
                entry_date: "2026-08-01",
                method: "UPI",
                reference: "",
                receipt_number: "SPT-R-0007",
                remarks: "",
              },
            ],
          },
        ]),
      ),
    );
    renderScreen(withGate(<PortalFeesPage />), { path: "/portal/fees", me: parent });

    const history = await screen.findByRole("list", { name: "Fee history 2026-27" });
    const items = within(history).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Payment · UPI");
    expect(items[0]).toHaveTextContent("Balance after: ₹5,000");
    expect(within(items[0]!).getByRole("button", { name: "Receipt" })).toBeInTheDocument();
    expect(items[1]).toHaveTextContent("Agreed fee");
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });
});

describe("filterNotes", () => {
  const note = (over: Partial<PortalNote>) =>
    ({
      id: 1,
      title: "",
      description: "",
      subject: "",
      subject_id: 1,
      standard: "",
      chapters: [],
      ...over,
    }) as PortalNote;
  const NOTES = [
    note({
      id: 1,
      title: "Quadratic formulas",
      subject: "Mathematics",
      subject_id: 21,
      chapters: ["4. Quadratic equations"],
    }),
    note({
      id: 2,
      title: "Reflection summary",
      subject: "Science",
      subject_id: 22,
      chapters: ["10. Light"],
    }),
  ];

  it("matches title, subject or chapter, and filters by subject", () => {
    expect(filterNotes(NOTES, "light", "").map((n) => n.id)).toEqual([2]);
    expect(filterNotes(NOTES, "MATH", "").map((n) => n.id)).toEqual([1]);
    expect(filterNotes(NOTES, "", "22").map((n) => n.id)).toEqual([2]);
    expect(filterNotes(NOTES, "quadratic", "22")).toEqual([]);
  });
});
