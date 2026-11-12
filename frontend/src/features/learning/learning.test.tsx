import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { API, fail, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { LearningDetailPage } from "./pages/LearningDetailPage";
import { LearningListPage } from "./pages/LearningListPage";
import { UploadPage } from "./pages/UploadPage";

const server = setupMockServer();

const REF = {
  boards: [{ id: 1, code: "CBSE", name: "Central Board", is_active: true }],
  standards: [{ id: 10, name: "Standard 10", level: 10, is_active: true }],
  subjects: [{ id: 21, name: "Mathematics", code: "MATH", is_active: true }],
  schools: [{ id: 3, name: "DPS", city: "Ahmedabad", is_active: true }],
  chapters: [{ id: 50, number: 1, name: "Real Numbers", is_active: true }],
};

const PAPER = {
  id: 9,
  title: "Real Numbers: unit test",
  description: "",
  board: 1,
  standard: 10,
  subject: 21,
  chapters: [50],
  semester: null,
  academic_year: 4,
  board_code: "CBSE",
  standard_name: "Standard 10",
  subject_name: "Mathematics",
  academic_year_name: "2026-27",
  chapter_names: ["Real Numbers"],
  school: null,
  test_date: null,
  max_marks: "25.00",
  duration_minutes: 60,
  is_archived: false,
  files: [
    {
      id: 1,
      kind: "PAPER",
      version: 1,
      original_name: "paper.pdf",
      size_bytes: 340000,
      uploaded_at: "2026-11-09T10:00:00+05:30",
    },
    {
      id: 2,
      kind: "ANSWER_KEY",
      version: 2,
      original_name: "key.pdf",
      size_bytes: 120000,
      uploaded_at: "2026-11-09T10:00:00+05:30",
    },
  ],
  active_assignments: 1,
  created_at: "2026-11-09T10:00:00+05:30",
};

const { max_marks: _m, duration_minutes: _d, test_date: _t, school: _s, ...NOTE_BASE } = PAPER;
const NOTE_ITEM = { ...NOTE_BASE, id: 5, title: "Summary notes" };

const ASSIGNMENT = {
  id: 70,
  student: { id: 7, admission_number: "SPT-2026-0012", first_name: "Aarav", last_name: "Shah" },
  test_paper: 9,
  test_title: PAPER.title,
  assigned_at: "2026-11-09T10:00:00+05:30",
  max_marks: "25.00",
  marks_obtained: null,
  grade_remarks: "",
};

/** Value of one multipart field (MSW can't parse jsdom File parts, so read the raw body). */
const field = (body: string, name: string) =>
  [
    ...body.matchAll(
      new RegExp(`name="${name}"(?:; filename="([^"]*)")?\r\n(?:[^\r\n]*\r\n)?\r\n([^\r]*)`, "g"),
    ),
  ].map((m) => m[1] ?? m[2]);

const pdf = (name = "paper.pdf") => new File(["%PDF-1.4"], name, { type: "application/pdf" });

beforeEach(() => {
  server.use(
    ...Object.entries(REF).map(([k, items]) =>
      http.get(`${API}/academics/${k}/`, () => ok(items, page(items.length))),
    ),
  );
});

describe("LearningListPage", () => {
  it("lists tests with their files and assignment count", async () => {
    server.use(http.get(`${API}/staff/tests/`, () => ok([PAPER], page(1))));
    renderScreen(<LearningListPage kind="tests" />, { path: "/staff/tests" });
    expect(
      await screen.findByRole("link", { name: /Real Numbers: unit test/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Paper + key (v2)")).toBeInTheDocument();
    expect(screen.getByText("1 students")).toBeInTheDocument();
  });
});

describe("UploadPage", () => {
  const renderUpload = () =>
    renderScreen(<UploadPage kind="tests" />, {
      path: "/staff/tests/new",
      extraRoutes: [{ path: "/staff/tests/:id", element: <p>detail page</p> }],
    });

  async function fill(user: ReturnType<typeof renderScreen>["user"]) {
    await user.upload(screen.getByLabelText("Question paper (required)"), pdf());
    await user.type(screen.getByLabelText("Title"), "Real Numbers: unit test");
    await user.selectOptions(await screen.findByLabelText("Board"), "1");
    await user.selectOptions(screen.getByLabelText("Standard"), "10");
    await user.selectOptions(screen.getByLabelText("Subject"), "21");
    await user.click(await screen.findByLabelText("1. Real Numbers"));
    await user.type(screen.getByLabelText("Max marks"), "25");
  }

  it("uploads as multipart with the chosen chapters, then opens the item ready to assign", async () => {
    let body = "";
    server.use(
      http.post(`${API}/staff/tests/`, async ({ request }) => {
        body = await request.text();
        return ok(PAPER);
      }),
    );
    const { user, router } = renderUpload();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText("detail page")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?assign=1");
    expect(field(body, "title")).toEqual(["Real Numbers: unit test"]);
    expect(field(body, "chapters")).toEqual(["50"]);
    expect(field(body, "max_marks")).toEqual(["25"]);
    expect(field(body, "file")).toEqual(["paper.pdf"]);
  });

  it("rejects a non-PDF in the browser", async () => {
    renderUpload();
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(
      screen.getByLabelText("Question paper (required)"),
      new File(["x"], "scan.jpg", { type: "image/jpeg" }),
    );
    expect(screen.getByText(/scan.jpg isn't a PDF/)).toBeInTheDocument();
  });

  it("same PDF already uploaded: asks, then resends with confirmation", async () => {
    const confirmations: (string | null)[] = [];
    server.use(
      http.post(`${API}/staff/tests/`, async ({ request }) => {
        const confirmed = field(await request.text(), "confirm_duplicate")[0] ?? null;
        confirmations.push(confirmed);
        return confirmed
          ? ok(PAPER)
          : fail(409, "DUPLICATE_DOCUMENT", "This exact PDF is already uploaded.");
      }),
    );
    const { user } = renderUpload();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Upload" }));
    await user.click(await screen.findByRole("button", { name: "Upload anyway" }));
    expect(await screen.findByText("detail page")).toBeInTheDocument();
    expect(confirmations).toEqual([null, "true"]);
  });
});

describe("LearningDetailPage (tests)", () => {
  const renderDetail = (path = "/staff/tests/9") =>
    renderScreen(<LearningDetailPage kind="tests" />, { path, route: "/staff/tests/:id" });

  beforeEach(() => {
    server.use(
      http.get(`${API}/staff/tests/9/`, () => ok(PAPER)),
      http.get(`${API}/staff/test-assignments/`, () => ok([ASSIGNMENT], page(1))),
    );
  });

  it("enters marks on leaving the box, and refuses marks above the maximum", async () => {
    const grades: unknown[] = [];
    server.use(
      http.post(`${API}/staff/test-assignments/70/grade/`, async ({ request }) => {
        grades.push(await request.json());
        return ok({ ...ASSIGNMENT, marks_obtained: "21.50" });
      }),
    );
    const { user } = renderDetail();
    const marks = await screen.findByLabelText("Marks for Aarav Shah");

    await user.type(marks, "27");
    await user.tab();
    expect(await screen.findByText("Must be between 0 and 25")).toBeInTheDocument();
    expect(grades).toEqual([]);

    await user.clear(marks);
    await user.type(marks, "21.5");
    await user.tab();
    await waitFor(() => expect(grades).toEqual([{ marks_obtained: "21.5", grade_remarks: "" }]));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("assign: class pre-selected, already-assigned hidden, start time sent, skipped students explained", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.get(`${API}/staff/students/`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        expect(params.get("standard")).toBe("10");
        expect(params.get("subject")).toBe("21");
        return ok([
          {
            id: 7,
            admission_number: "A7",
            first_name: "Aarav",
            last_name: "Shah",
            board_code: "CBSE",
            standard_name: "Standard 10",
            school_name: "DPS",
          },
          {
            id: 8,
            admission_number: "A8",
            first_name: "Riya",
            last_name: "Shah",
            board_code: "CBSE",
            standard_name: "Standard 10",
            school_name: "DPS",
          },
          {
            id: 9,
            admission_number: "A9",
            first_name: "Om",
            last_name: "Bhatt",
            board_code: "CBSE",
            standard_name: "Standard 10",
            school_name: "DPS",
          },
        ]);
      }),
      http.post(`${API}/staff/tests/9/assign/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ assigned: [{}], failed: [{ student_id: 9, reason: "STUDENT_NOT_ACTIVE" }] });
      }),
    );
    const { user } = renderDetail("/staff/tests/9?assign=1");
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Riya Shah")).toBeInTheDocument();
    expect(within(dialog).queryByText("Aarav Shah")).not.toBeInTheDocument(); // already assigned
    await user.type(within(dialog).getByLabelText("Test starts (optional)"), "2026-11-11T16:00");
    await user.click(within(dialog).getByRole("button", { name: "Assign to 2" }));

    expect(await screen.findByText(/Om Bhatt: not an active student/)).toBeInTheDocument();
    expect(body.student_ids).toEqual([8, 9]);
    expect(body.duration_minutes).toBe(60);
    expect(typeof body.test_starts_at).toBe("string");
  });
});

describe("LearningDetailPage (notes)", () => {
  it("shows students without a marks grid", async () => {
    server.use(
      http.get(`${API}/staff/notes/5/`, () =>
        ok({ ...NOTE_ITEM, files: [{ ...PAPER.files[0], kind: "NOTE" }] }),
      ),
      http.get(`${API}/staff/note-assignments/`, () => ok([{ ...ASSIGNMENT, note: 5 }], page(1))),
    );
    renderScreen(<LearningDetailPage kind="notes" />, {
      path: "/staff/notes/5",
      route: "/staff/notes/:id",
    });
    expect(await screen.findByText("Aarav Shah")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Marks for/)).not.toBeInTheDocument();
    expect(screen.getByText("Notes PDF")).toBeInTheDocument();
  });
});
