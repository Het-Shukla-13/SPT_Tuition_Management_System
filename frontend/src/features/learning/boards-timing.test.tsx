import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { LearningDetailPage } from "./pages/LearningDetailPage";
import { LearningListPage } from "./pages/LearningListPage";
import { timingBody, timingFrom, timingSummary } from "./timing";

const server = setupMockServer();

const PAPER = {
  id: 9,
  title: "Real Numbers: unit test",
  description: "",
  boards: [],
  board_codes: [],
  standard: 10,
  subject: 21,
  chapters: [],
  semester: null,
  standard_name: "Standard 10",
  subject_name: "Mathematics",
  academic_year_name: "2026-27",
  chapter_names: [],
  school: null,
  test_date: null,
  max_marks: "25.00",
  duration_minutes: 60,
  is_archived: false,
  files: [],
  active_assignments: 2,
  created_at: "2026-11-09T10:00:00+05:30",
};

const row = (id: number, name: string, over: Record<string, unknown>) => ({
  id,
  student: { id, admission_number: `A${id}`, first_name: name, last_name: "Shah" },
  test_paper: 9,
  test_title: PAPER.title,
  assigned_at: "2026-11-09T10:00:00+05:30",
  max_marks: "25.00",
  marks_obtained: null,
  grade_remarks: "",
  duration_minutes: 60,
  ...over,
});

const UPCOMING = row(70, "Aarav", {
  test_starts_at: "2099-01-10T10:00:00+05:30",
  has_start_time: true,
  visible_from: "2099-01-10T10:00:00+05:30",
  test_ends_at: "2099-01-10T11:00:00+05:30",
  is_over: false,
});
const DATE_ONLY = row(71, "Riya", {
  test_starts_at: "2099-01-11T08:00:00+05:30",
  has_start_time: false,
  visible_from: "2099-01-11T08:00:00+05:30",
  test_ends_at: null,
  is_over: false,
});

beforeEach(() => {
  server.use(
    http.get(`${API}/academics/academic-years/`, () =>
      ok(
        [
          {
            id: 1,
            board: 1,
            name: "2026-27",
            start_date: "2026-04-01",
            is_current: true,
            is_active: true,
          },
        ],
        page(1),
      ),
    ),
    http.get(`${API}/academics/boards/`, () =>
      ok([{ id: 1, code: "CBSE", name: "Central Board", is_active: true }], page(1)),
    ),
    http.get(`${API}/academics/standards/`, () => ok([], page(0))),
    http.get(`${API}/academics/subjects/`, () => ok([], page(0))),
  );
});

describe("A test for every board", () => {
  it("shows 'All boards' and the year on the test's page", async () => {
    server.use(
      http.get(`${API}/staff/tests/9/`, () => ok(PAPER)),
      http.get(`${API}/staff/test-assignments/`, () => ok([], page(0))),
    );
    renderScreen(<LearningDetailPage kind="tests" />, {
      path: "/staff/tests/9",
      route: "/staff/tests/:id",
    });
    expect(await screen.findByText(/Standard 10 · All boards · Mathematics/)).toBeInTheDocument();
    expect(screen.getByText("2026-27")).toBeInTheDocument();
  });
});

describe("Students & marks: timing", () => {
  const renderDetail = () => {
    server.use(
      http.get(`${API}/staff/tests/9/`, () => ok(PAPER)),
      http.get(`${API}/staff/test-assignments/`, () => ok([UPCOMING, DATE_ONLY], page(2))),
    );
    return renderScreen(<LearningDetailPage kind="tests" />, {
      path: "/staff/tests/9",
      route: "/staff/tests/:id",
    });
  };

  it("shows each student's test time and keeps marks closed until the test is over", async () => {
    renderDetail();
    expect(await screen.findByText(/from 8:00 am/)).toBeInTheDocument();
    expect(screen.getByLabelText("Marks for Aarav Shah")).toBeDisabled();
    expect(screen.getByLabelText("Marks for Aarav Shah")).toHaveAttribute(
      "placeholder",
      "After test",
    );
  });

  it("edits the time for the selected students", async () => {
    const patches: { id: string; body: unknown }[] = [];
    server.use(
      http.patch(`${API}/staff/test-assignments/:id/`, async ({ request, params }) => {
        patches.push({ id: String(params.id), body: await request.json() });
        return ok(UPCOMING);
      }),
    );
    const { user } = renderDetail();
    await user.click(await screen.findByLabelText("Select Aarav Shah"));
    await user.click(screen.getByLabelText("Select Riya Shah"));
    await user.click(screen.getByRole("button", { name: "Edit time (2)" }));

    const dialog = await screen.findByRole("dialog", { name: "Edit test time (2 students)" });
    const date = within(dialog).getByLabelText("Test date (optional)");
    await user.clear(date);
    await user.type(date, "2099-02-01");
    const time = within(dialog).getByLabelText("Start time (optional)");
    await user.clear(time);
    expect(within(dialog).getByText(/8:00 AM on that date/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patches).toHaveLength(2));
    expect(patches.map((p) => p.id).sort()).toEqual(["70", "71"]);
    expect(patches[0]?.body).toEqual({
      test_date: "2099-02-01",
      test_time: null,
      duration_minutes: 60,
    });
  });
});

describe("Bulk archive", () => {
  it("archives the ticked tests from the list", async () => {
    let body: unknown;
    server.use(
      http.get(`${API}/staff/tests/`, () =>
        ok([PAPER, { ...PAPER, id: 10, title: "Light test" }], page(2)),
      ),
      http.post(`${API}/staff/tests/bulk-archive/`, async ({ request }) => {
        body = await request.json();
        return ok({ done: [9, 10], failed: [] });
      }),
    );
    const { user } = renderScreen(<LearningListPage kind="tests" />, { path: "/staff/tests" });
    await screen.findByLabelText("Select Light test"); // rows are in
    await user.click(screen.getByLabelText("Select all on this page"));
    const bar = screen.getByRole("region", { name: "Selected" });
    expect(bar).toHaveTextContent("2 selected");
    await user.click(within(bar).getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(body).toEqual({ ids: [9, 10], archived: true }));
  });
});

describe("timing helpers", () => {
  it("builds the request and describes when the paper opens", () => {
    expect(timingBody({ date: "", time: "10:00", duration: "" })).toEqual({
      test_date: null,
      test_time: null,
      duration_minutes: null,
    });
    expect(timingBody({ date: "2099-01-10", time: "10:00", duration: "45" })).toEqual({
      test_date: "2099-01-10",
      test_time: "10:00",
      duration_minutes: 45,
    });
    expect(timingSummary({ date: "", time: "", duration: "" })).toMatch(/straight away/);
    expect(timingSummary({ date: "2099-01-10", time: "", duration: "" })).toMatch(/8:00 AM/);
    expect(timingFrom(null, true, "60")).toEqual({ date: "", time: "", duration: "60" });
  });
});
