import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, fail, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { AdmissionPage } from "./pages/AdmissionPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";
import { StudentsPage } from "./pages/StudentsPage";

const server = setupMockServer();

const REF = {
  boards: [{ id: 1, code: "CBSE", name: "Central Board", is_active: true }],
  standards: [{ id: 10, name: "Standard 10", level: 10, is_active: true }],
  schools: [{ id: 3, name: "DPS", city: "Ahmedabad", is_active: true }],
  subjects: [
    { id: 21, name: "Mathematics", code: "MATH", is_active: true },
    { id: 22, name: "Science", code: "SCI", is_active: true },
  ],
};

const STUDENT = {
  id: 7,
  admission_number: "SPT-2026-0012",
  first_name: "Aarav",
  last_name: "Shah",
  board: { id: 1, code: "CBSE", name: "Central Board" },
  standard: { id: 10, name: "Standard 10", level: 10 },
  school: { id: 3, name: "DPS", city: "Ahmedabad" },
  status: "ACTIVE",
  admission_date: "2026-06-01",
  guardian_name: "Kavita Shah",
  guardian_phone: "+919876543210",
  guardian_relation: "Mother",
  guardian_email: "",
  date_of_birth: "2011-05-10",
  gender: "MALE",
  address: "",
  remarks: "",
  left_on: null,
  subjects: [
    {
      subject: { id: 21, name: "Mathematics", code: "MATH" },
      started_on: "2026-06-01",
      ended_on: null,
    },
  ],
  logins: [
    {
      user_id: 40,
      first_name: "Kavita",
      last_name: "Shah",
      email: "kavita@example.com",
      phone: null,
      invite_accepted: true,
    },
  ],
  has_photo: false,
  created_at: "2026-06-01T10:00:00+05:30",
};

beforeEach(() => {
  server.use(
    ...Object.entries(REF).map(([key, items]) =>
      http.get(`${API}/academics/${key}/`, () => ok(items, page(items.length))),
    ),
  );
});

describe("StudentsPage", () => {
  it("lists active students by default and searches through the API", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/students/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok([STUDENT], page(1));
      }),
    );
    const { user } = renderScreen(<StudentsPage />, { path: "/staff/students" });
    expect(await screen.findByText("Aarav Shah")).toBeInTheDocument();
    expect(seen[0]?.get("status")).toBe("ACTIVE");

    await user.type(screen.getByRole("searchbox"), "kavita");
    await waitFor(() => expect(seen.at(-1)?.get("search")).toBe("kavita"));
  });
});

async function fillAdmission(user: ReturnType<typeof renderScreen>["user"]) {
  await user.type(screen.getByLabelText("First name"), "Riya");
  await user.type(screen.getByLabelText("Last name"), "Shah");
  await user.selectOptions(await screen.findByLabelText("Board"), "1");
  await user.selectOptions(screen.getByLabelText("Standard"), "10");
  await user.selectOptions(screen.getByLabelText("School"), "3");
  await user.click(await screen.findByLabelText("Mathematics"));
  await user.type(screen.getByLabelText("Guardian name"), "Kavita Shah");
  await user.type(screen.getByLabelText("Phone"), "9876543210");
}

describe("AdmissionPage from an enquiry", () => {
  const ENQUIRY = {
    id: 12,
    parent_name: "Kavita Shah",
    phone: "+919876543210",
    email: "kavita@example.com",
    student_name: "Riya Kumari Shah",
    standard: 10,
    standard_name: "Standard 10",
    board: 1,
    board_code: "CBSE",
    medium: "GUJARATI",
    school_name: "DPS Bopal",
    message: "Maths and science, evenings",
    source: "WALK_IN",
    status: "CONTACTED",
    notes: "",
    handled_by: null,
    student: null,
    created_at: "2026-11-01T10:00:00+05:30",
    updated_at: "2026-11-01T10:00:00+05:30",
  };

  it("starts from the enquiry and links the admitted student back to it", async () => {
    let linked: unknown;
    server.use(
      http.get(`${API}/admin/enquiries/12/`, () => ok(ENQUIRY)),
      http.post(`${API}/admin/students/`, () =>
        ok({ student: { ...STUDENT, id: 8 }, invite_sent: {} }),
      ),
      http.patch(`${API}/admin/enquiries/12/`, async ({ request }) => {
        linked = await request.json();
        return ok({ ...ENQUIRY, status: "ACCEPTED", student: 8 });
      }),
    );
    const { user } = renderScreen(<AdmissionPage />, {
      path: "/staff/students/new?enquiry=12",
      extraRoutes: [{ path: "/staff/students/:id", element: <p>profile page</p> }],
    });

    expect(await screen.findByLabelText("First name")).toHaveValue("Riya");
    expect(screen.getByLabelText("Last name")).toHaveValue("Kumari Shah");
    expect(screen.getByLabelText("Guardian name")).toHaveValue("Kavita Shah");
    expect(screen.getByText(/Started from Kavita Shah's enquiry/)).toBeInTheDocument();
    expect(screen.getByLabelText("Medium (optional)")).toHaveValue("GUJARATI");
    expect(screen.getByText("The enquiry says:", { exact: false })).toHaveTextContent(
      "The enquiry says: DPS Bopal.",
    );
    await waitFor(() => expect(screen.getByLabelText("Board")).toHaveValue("1"));

    await user.selectOptions(screen.getByLabelText("School"), "3");
    await user.click(await screen.findByLabelText("Mathematics"));
    await user.click(screen.getByRole("button", { name: "Admit student" }));

    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(linked).toEqual({ student: 8 });
  });
});

describe("AdmissionPage", () => {
  const renderAdmission = () =>
    renderScreen(<AdmissionPage />, {
      path: "/staff/students/new",
      extraRoutes: [{ path: "/staff/students/:id", element: <p>profile page</p> }],
    });

  it("checks required parts before calling the server", async () => {
    const { user } = renderAdmission();
    await user.click(screen.getByRole("button", { name: "Admit student" }));
    expect(await screen.findByText("Enter the first name.")).toBeInTheDocument();
    expect(screen.getByText("Choose a board.")).toBeInTheDocument();
    expect(screen.getByText("Choose at least one subject.")).toBeInTheDocument();
  });

  it("admits with a new parent login prefilled from the guardian, then opens the profile", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API}/admin/students/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ student: { ...STUDENT, id: 8 }, invite_sent: {} }, null);
      }),
    );
    const { user } = renderAdmission();
    await fillAdmission(user);
    await user.click(screen.getByRole("button", { name: "+ Add a new login" }));
    const login = screen.getByText("New login 1").closest("div")!.parentElement!;
    expect(within(login).getByLabelText("First name")).toHaveValue("Kavita");
    await user.type(within(login).getByLabelText("Email"), "kavita@example.com");
    await user.click(screen.getByRole("button", { name: "Admit student" }));

    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(body).toMatchObject({
      first_name: "Riya",
      board: 1,
      standard: 10,
      school: 3,
      subjects: [21],
      guardian_phone: "9876543210",
      new_logins: [
        {
          first_name: "Kavita",
          last_name: "Shah",
          email: "kavita@example.com",
          phone: "9876543210",
        },
      ],
      link_user_ids: [],
      confirm_duplicate: false,
    });
  });

  it("possible duplicate: shows the look-alikes, and 'admit anyway' resends with confirmation", async () => {
    const bodies: Record<string, unknown>[] = [];
    server.use(
      http.post(`${API}/admin/students/`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);
        if (!body.confirm_duplicate) {
          return fail(409, "POSSIBLE_DUPLICATE_STUDENT", "A similar student already exists.", {
            possible_duplicates: [
              {
                id: 7,
                admission_number: "SPT-2026-0012",
                name: "Aarav Shah",
                standard: "Standard 10",
                date_of_birth: null,
                status: "ACTIVE",
              },
            ],
          });
        }
        return ok({ student: { ...STUDENT, id: 8 }, invite_sent: {} });
      }),
    );
    const { user } = renderAdmission();
    await fillAdmission(user);
    await user.click(screen.getByRole("button", { name: "Admit student" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("link", { name: "Aarav Shah" })).toHaveAttribute(
      "href",
      "/staff/students/7",
    );
    await user.click(within(alert).getByRole("button", { name: /admit anyway/ }));

    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(bodies.map((b) => b.confirm_duplicate)).toEqual([false, true]);
  });

  it("shows server errors on the right new login", async () => {
    server.use(
      http.post(`${API}/admin/students/`, () =>
        fail(400, "VALIDATION_ERROR", "Validation failed.", {
          new_logins: [{ email: ["This email is already used by another account."] }],
        }),
      ),
    );
    const { user } = renderAdmission();
    await fillAdmission(user);
    await user.click(screen.getByRole("button", { name: "+ Add a new login" }));
    await user.type(screen.getAllByLabelText("Email").at(-1)!, "taken@example.com");
    await user.click(screen.getByRole("button", { name: "Admit student" }));
    expect(
      await screen.findByText("This email is already used by another account."),
    ).toBeInTheDocument();
  });
});

describe("StudentDetailPage", () => {
  const renderDetail = () =>
    renderScreen(<StudentDetailPage />, {
      path: "/staff/students/7",
      route: "/staff/students/:id",
    });

  beforeEach(() => {
    server.use(
      http.get(`${API}/admin/students/7/`, () => ok(STUDENT)),
      http.get(`${API}/admin/students/7/history/`, () =>
        ok([
          {
            id: 1,
            academic_year: "2026-27",
            board: "CBSE",
            standard: "Standard 10",
            school: "DPS, Ahmedabad",
            started_on: "2026-06-01",
            ended_on: null,
            reason: "ADMISSION",
          },
        ]),
      ),
      http.get(`${API}/admin/fees/students/7/accounts/`, () =>
        ok([
          {
            id: 3,
            board: "CBSE",
            academic_year_name: "2026-27",
            standard: "Standard 10",
            total: "20000.00",
            paid: "5000.00",
            pending: "15000.00",
            status: "DUE",
          },
        ]),
      ),
    );
  });

  it("shows details, fees, subjects, logins and history", async () => {
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Aarav Shah" })).toBeInTheDocument();
    expect(await screen.findByText("₹15,000")).toBeInTheDocument();
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("kavita@example.com")).toBeInTheDocument();
    expect(await screen.findByText(/2026-27 · CBSE · Standard 10/)).toBeInTheDocument();
  });

  it("changes subjects", async () => {
    let body: unknown;
    server.use(
      http.post(`${API}/admin/students/7/subjects/`, async ({ request }) => {
        body = await request.json();
        return ok(STUDENT);
      }),
    );
    const { user } = renderDetail();
    await user.click(await screen.findByRole("button", { name: "Change" }));
    await user.click(await screen.findByLabelText("Science"));
    await user.click(screen.getByRole("button", { name: "Save subjects" }));
    await waitFor(() => expect(body).toEqual({ subjects: [21, 22] }));
  });

  it("change class sends only what changed, with the reason", async () => {
    let body: unknown;
    server.use(
      http.post(`${API}/admin/students/7/academic/`, async ({ request }) => {
        body = await request.json();
        return ok(STUDENT);
      }),
      http.get(`${API}/academics/standards/`, () =>
        ok(
          [...REF.standards, { id: 11, name: "Standard 11", level: 11, is_active: true }],
          page(2),
        ),
      ),
    );
    const { user } = renderDetail();
    await user.click(await screen.findByRole("button", { name: "Change class" }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByLabelText("Standard")).not.toBeDisabled());
    await user.selectOptions(within(dialog).getByLabelText("Standard"), "11");
    await user.click(within(dialog).getByRole("button", { name: "Change class" }));
    await waitFor(() => expect(body).toEqual({ reason: "PROMOTION", standard: 11 }));
  });

  it("removes a login's access after confirming", async () => {
    let called = false;
    server.use(
      http.delete(`${API}/admin/students/7/access/40/`, () => {
        called = true;
        return ok(STUDENT);
      }),
    );
    const { user } = renderDetail();
    await user.click(await screen.findByRole("button", { name: "Remove" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove access" }),
    );
    await waitFor(() => expect(called).toBe(true));
  });
});

describe("AdmissionPage optional subject fees", () => {
  it("adds the fee structure's extra for an optional subject, with an editable amount", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.get(`${API}/admin/fee-structures/`, () =>
        ok(
          [
            {
              id: 9,
              total_fee: "20000.00",
              add_ons: [{ subject: 22, subject_name: "Science", amount: "1500.00" }],
            },
          ],
          page(1),
        ),
      ),
      http.post(`${API}/admin/students/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ student: { ...STUDENT, id: 8 }, invite_sent: {} });
      }),
    );
    const { user } = renderScreen(<AdmissionPage />, {
      path: "/staff/students/new",
      extraRoutes: [{ path: "/staff/students/:id", element: <p>profile page</p> }],
    });
    await fillAdmission(user);
    expect(screen.queryByLabelText("Science fee")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Science"));
    const fee = await screen.findByLabelText("Science fee");
    expect(fee).toHaveValue("1500");
    expect(screen.getByText(/fee structure: ₹20,000/)).toBeInTheDocument();
    await user.clear(fee);
    await user.type(fee, "1000");
    await user.click(screen.getByRole("button", { name: "Admit student" }));

    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(body.subject_fees).toEqual([{ subject: 22, amount: "1000" }]);
  });
});
