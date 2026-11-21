import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { cleanGuardians, validateGuardians } from "./guardians";
import { AdmissionPage } from "./pages/AdmissionPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";

const server = setupMockServer();

const REF = {
  boards: [{ id: 1, code: "CBSE", name: "Central Board", is_active: true }],
  standards: [{ id: 10, name: "Standard 10", level: 10, is_active: true }],
  schools: [{ id: 3, name: "DPS", city: "Ahmedabad", is_active: true }],
  subjects: [{ id: 21, name: "Mathematics", code: "MATH", is_active: true }],
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
  guardians: [
    { id: 1, name: "Kavita Shah", relation: "Mother", phone: "+919876543210", email: "" },
    {
      id: 2,
      name: "Rohan Shah",
      relation: "Father",
      phone: "+919123456780",
      email: "rohan@example.com",
    },
  ],
  date_of_birth: null,
  gender: "",
  medium: "",
  address: "",
  remarks: "",
  left_on: null,
  subjects: [],
  logins: [],
  has_photo: false,
  created_at: "2026-06-01T10:00:00+05:30",
};

beforeEach(() => {
  server.use(
    ...Object.entries(REF).map(([key, items]) =>
      http.get(`${API}/academics/${key}/`, () => ok(items, page(items.length))),
    ),
    http.get(`${API}/admin/fee-structures/`, () => ok([], page(0))),
  );
});

describe("Guardians at admission", () => {
  it("sends every guardian, and pre-fills the second login from the second guardian", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API}/admin/students/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ student: { ...STUDENT, id: 8 }, invite_sent: {} });
      }),
    );
    const { user } = renderScreen(<AdmissionPage />, {
      path: "/staff/students/new",
      extraRoutes: [{ path: "/staff/students/:id", element: <p>profile page</p> }],
    });
    await user.type(screen.getByLabelText("First name"), "Riya");
    await user.type(screen.getByLabelText("Last name"), "Shah");
    await user.selectOptions(await screen.findByLabelText("Board"), "1");
    await user.selectOptions(screen.getByLabelText("Standard"), "10");
    await user.selectOptions(screen.getByLabelText("School"), "3");
    await user.click(await screen.findByLabelText("Mathematics"));

    const main = screen.getByRole("group", { name: /Main guardian/ });
    await user.type(within(main).getByLabelText("Name"), "Kavita Shah");
    await user.type(within(main).getByLabelText("Relation"), "Mother");
    await user.type(within(main).getByLabelText("Phone"), "9876543210");
    await user.click(screen.getByRole("button", { name: "+ Add another guardian" }));
    const second = screen.getByRole("group", { name: /Guardian 2/ });
    await user.type(within(second).getByLabelText("Name"), "Rohan Shah");
    await user.type(within(second).getByLabelText("Relation"), "Father");
    await user.type(within(second).getByLabelText("Email (optional)"), "rohan@example.com");

    // Two new logins: one per guardian.
    await user.click(screen.getByRole("button", { name: "+ Add a new login" }));
    await user.click(screen.getByRole("button", { name: "+ Add a new login" }));
    const login2 = screen.getByText("New login 2").closest("div")!.parentElement!;
    expect(within(login2).getByLabelText("First name")).toHaveValue("Rohan");
    expect(within(login2).getByLabelText("Email")).toHaveValue("rohan@example.com");
    const login1 = screen.getByText("New login 1").closest("div")!.parentElement!;
    await user.type(within(login1).getByLabelText("Email"), "kavita@example.com");
    // No fee structure for this standard: the fee has to be typed.
    await user.type(screen.getByLabelText("Standard fee (without optional subjects)"), "20000");

    await user.click(screen.getByRole("button", { name: "Admit student" }));
    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(body.guardians).toEqual([
      { name: "Kavita Shah", relation: "Mother", phone: "9876543210", email: "" },
      { name: "Rohan Shah", relation: "Father", phone: "", email: "rohan@example.com" },
    ]);
  }, 20_000); // a long form to fill: give it time when the whole suite runs in parallel

  it("a guardian with details needs a name", async () => {
    let called = false;
    server.use(
      http.post(`${API}/admin/students/`, () => {
        called = true;
        return ok({});
      }),
    );
    const { user } = renderScreen(<AdmissionPage />, { path: "/staff/students/new" });
    await user.type(screen.getByLabelText("First name"), "Riya");
    await user.type(screen.getByLabelText("Last name"), "Shah");
    await user.selectOptions(await screen.findByLabelText("Board"), "1");
    await user.selectOptions(screen.getByLabelText("Standard"), "10");
    await user.selectOptions(screen.getByLabelText("School"), "3");
    await user.click(await screen.findByLabelText("Mathematics"));
    const main = screen.getByRole("group", { name: /Main guardian/ });
    await user.type(within(main).getByLabelText("Phone"), "9876543210");
    await user.click(screen.getByRole("button", { name: "Admit student" }));

    expect(await within(main).findByText("Enter the guardian's name.")).toBeInTheDocument();
    expect(called).toBe(false);
  });
});

describe("Guardians on the student page", () => {
  const renderDetail = () => {
    server.use(
      http.get(`${API}/admin/students/7/`, () => ok(STUDENT)),
      http.get(`${API}/admin/fees/students/7/accounts/`, () => ok([])),
      http.get(`${API}/admin/students/7/history/`, () => ok([])),
    );
    return renderScreen(<StudentDetailPage />, {
      path: "/staff/students/7",
      route: "/staff/students/:id",
    });
  };

  it("lists every guardian and edits the list", async () => {
    let patch: Record<string, unknown> = {};
    server.use(
      http.patch(`${API}/admin/students/7/`, async ({ request }) => {
        patch = (await request.json()) as Record<string, unknown>;
        return ok(STUDENT);
      }),
    );
    const { user } = renderDetail();

    expect(await screen.findByText("Main guardian")).toBeInTheDocument();
    expect(screen.getByText("Guardian 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /91234/ })).toHaveAttribute(
      "href",
      "tel:+919123456780",
    );

    await user.click(screen.getByRole("button", { name: /Edit details/ }));
    const dialog = await screen.findByRole("dialog", { name: "Edit details" });
    await user.click(within(dialog).getByRole("button", { name: "Remove guardian 2" }));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(patch.guardians).toEqual([
        { name: "Kavita Shah", relation: "Mother", phone: "+919876543210", email: "" },
      ]),
    );
  });
});

describe("guardian helpers", () => {
  it("drops empty rows and checks the rest", () => {
    const rows = [
      { name: " Kavita ", relation: "", phone: "", email: "" },
      { name: "", relation: "", phone: "", email: "" },
      { name: "", relation: "Father", phone: "12", email: "bad" },
    ];
    expect(cleanGuardians(rows)).toHaveLength(2);
    expect(validateGuardians(rows)).toEqual({
      "2.name": "Enter the guardian's name.",
      "2.email": "Enter a valid email address.",
      "2.phone": "Enter a 10-digit mobile number.",
    });
  });
});
