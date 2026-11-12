import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { splitName } from "./api";
import { EnquiriesPage } from "./pages/EnquiriesPage";
import { EnquiryDetailPage } from "./pages/EnquiryDetailPage";
import { PublicEnquiryPage } from "./pages/PublicEnquiryPage";

const server = setupMockServer();

const ENQUIRY = {
  id: 12,
  parent_name: "Kavita Shah",
  phone: "+919876543210",
  email: "",
  student_name: "Riya Shah",
  standard: 10 as number | null,
  standard_name: "Standard 10",
  board: 1 as number | null,
  board_code: "CBSE",
  message: "Evening batch?",
  status: "NEW",
  notes: "",
  handled_by: null,
  student: null as number | null,
  created_at: "2026-11-01T10:00:00+05:30",
  updated_at: "2026-11-01T10:00:00+05:30",
};

beforeEach(() => {
  server.use(
    http.get(`${API}/academics/boards/`, () =>
      ok([{ id: 1, code: "CBSE", name: "Central Board" }], page(1)),
    ),
    http.get(`${API}/academics/standards/`, () =>
      ok([{ id: 10, name: "Standard 10", level: 10 }], page(1)),
    ),
  );
});

describe("EnquiriesPage", () => {
  it("lists enquiries and filters by status through the API", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/enquiries/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok([ENQUIRY], page(1));
      }),
    );
    const { user, search } = renderScreen(<EnquiriesPage />, { path: "/staff/enquiries" });

    const row = (await screen.findByRole("link", { name: /Riya Shah/ })).closest("tr")!;
    expect(row).toHaveTextContent("Standard 10 · CBSE");
    expect(within(row).getByRole("link", { name: /98765/ })).toHaveAttribute(
      "href",
      "tel:+919876543210",
    );

    await user.selectOptions(screen.getByLabelText("Status"), "NEW");
    await waitFor(() => expect(seen.at(-1)?.get("status")).toBe("NEW"));
    expect(search()).toContain("status=NEW");
  });
});

describe("EnquiryDetailPage", () => {
  const renderDetail = (enquiry = ENQUIRY) => {
    server.use(http.get(`${API}/admin/enquiries/12/`, () => ok(enquiry)));
    return renderScreen(<EnquiryDetailPage />, {
      path: "/staff/enquiries/12",
      route: "/staff/enquiries/:id",
    });
  };

  it("saves the follow-up status and notes", async () => {
    let body: unknown;
    server.use(
      http.patch(`${API}/admin/enquiries/12/`, async ({ request }) => {
        body = await request.json();
        return ok({
          ...ENQUIRY,
          status: "CONTACTED",
          notes: "Visiting Saturday",
          updated_at: "2026-11-02T10:00:00+05:30",
        });
      }),
    );
    const { user } = renderDetail();
    const save = await screen.findByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Status"), "CONTACTED");
    await user.type(screen.getByLabelText("Notes (only staff see these)"), "Visiting Saturday");
    await user.click(save);
    await waitFor(() => expect(body).toEqual({ status: "CONTACTED", notes: "Visiting Saturday" }));
  });

  it("offers to admit the student from the enquiry", async () => {
    renderDetail();
    expect(await screen.findByRole("link", { name: "Admit this student" })).toHaveAttribute(
      "href",
      "/staff/students/new?enquiry=12",
    );
  });

  it("links an admitted enquiry to its student and locks the status", async () => {
    renderDetail({ ...ENQUIRY, status: "ACCEPTED", student: 8 });
    expect(await screen.findByRole("link", { name: "Open admitted student" })).toHaveAttribute(
      "href",
      "/staff/students/8",
    );
    expect(screen.queryByRole("link", { name: "Admit this student" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeDisabled();
  });
});

describe("PublicEnquiryPage", () => {
  it("offers the boards and standards, sends the request and thanks the family", async () => {
    let body: Record<string, unknown> | undefined;
    server.use(
      http.get(`${API}/public/enquiries/options/`, () =>
        ok({
          boards: [{ id: 1, code: "CBSE", name: "Central Board" }],
          standards: [{ id: 10, name: "Standard 10" }],
        }),
      ),
      http.post(`${API}/public/enquiries/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok(null);
      }),
    );
    const { user } = renderScreen(<PublicEnquiryPage />, { path: "/enquire" });

    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Enter your name.")).toBeInTheDocument();
    expect(body).toBeUndefined();

    await user.type(screen.getByLabelText("Your name"), "Kavita Shah");
    await user.type(screen.getByLabelText("Mobile number"), "98765 43210");
    await user.type(screen.getByLabelText("Student's name"), "Riya");
    const standard = screen.getByLabelText("Standard (optional)");
    await waitFor(() =>
      expect(within(standard).getByRole("option", { name: "Standard 10" })).toBeInTheDocument(),
    );
    await user.selectOptions(standard, "10");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Thank you, Kavita Shah!")).toBeInTheDocument();
    expect(body).toMatchObject({
      parent_name: "Kavita Shah",
      phone: "98765 43210",
      student_name: "Riya",
      standard: 10,
      board: null,
      website: "",
    });
  });
});

describe("splitName", () => {
  it("keeps the first word as the first name", () => {
    expect(splitName("  Riya  Kumari Shah ")).toEqual({ first: "Riya", last: "Kumari Shah" });
    expect(splitName("Riya")).toEqual({ first: "Riya", last: "" });
  });
});
