import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { entryLabel } from "./api";
import { StructuresTab } from "./components/StructuresTab";
import { SubjectFeeFollowUp } from "./components/SubjectFeeFollowUp";

const server = setupMockServer();

const GUJ = { id: 31, name: "Gujarati", code: "GUJ", is_active: true };
const HIN = { id: 32, name: "Hindi", code: "HIN", is_active: true };

beforeEach(() => {
  server.use(
    http.get(`${API}/academics/academic-years/`, () =>
      ok(
        [
          {
            id: 1,
            board: 1,
            board_code: "CBSE",
            name: "2026-27",
            start_date: "2026-04-01",
            is_current: true,
            is_active: true,
          },
          {
            id: 2,
            board: 2,
            board_code: "GSEB",
            name: "2026-27",
            start_date: "2026-06-01",
            is_current: true,
            is_active: true,
          },
          {
            id: 3,
            board: 2,
            board_code: "GSEB",
            name: "2027-28",
            start_date: "2027-06-01",
            is_current: false,
            is_active: true,
          },
        ],
        page(3),
      ),
    ),
    http.get(`${API}/academics/boards/`, () =>
      ok(
        [
          { id: 1, code: "CBSE", name: "Central Board", is_active: true },
          { id: 2, code: "GSEB", name: "Gujarat Board", is_active: true },
        ],
        page(2),
      ),
    ),
    http.get(`${API}/academics/standards/`, () =>
      ok([{ id: 10, name: "Standard 10", level: 10, is_active: true }], page(1)),
    ),
    http.get(`${API}/academics/subjects/`, () => ok([GUJ, HIN], page(2))),
  );
});

describe("Fee structures with optional subject fees", () => {
  it("picks the board, then that board's year (current first), and saves the extras", async () => {
    let body: Record<string, unknown> | undefined;
    server.use(
      http.get(`${API}/admin/fee-structures/`, () => ok([], page(0))),
      http.post(`${API}/admin/fee-structures/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ id: 5 });
      }),
    );
    const { user } = renderScreen(<StructuresTab />, { path: "/staff/fees?tab=structures" });

    await user.click(screen.getByRole("button", { name: "+ Add fee structure" }));
    const dialog = await screen.findByRole("dialog", { name: "Add fee structure" });
    const year = within(dialog).getByLabelText("Academic year");
    expect(year).toBeDisabled(); // a board comes first
    const board = within(dialog).getByLabelText("Board");
    await waitFor(() =>
      expect(within(board).getByRole("option", { name: /GSEB/ })).toBeInTheDocument(),
    );
    await user.selectOptions(board, "2");
    // Only GSEB's years, by plain name, starting on its current one.
    expect(year).toHaveValue("2");
    expect(
      within(year)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Choose…", "2027-28", "2026-27 (current)"]);
    expect(within(dialog).getByRole("link", { name: "Add a subject" })).toHaveAttribute(
      "href",
      "/staff/academics?tab=subjects",
    );
    await user.selectOptions(within(dialog).getByLabelText("Standard"), "10");
    await user.type(
      within(dialog).getByLabelText("Standard fee (for the included subjects)"),
      "20000",
    );

    await user.click(within(dialog).getByRole("button", { name: "+ Add optional subject fee" }));
    const subject = within(dialog).getByLabelText("Optional subject 1");
    await waitFor(() =>
      expect(within(subject).getByRole("option", { name: "Gujarati" })).toBeInTheDocument(),
    );
    await user.selectOptions(subject, "31");
    await user.type(within(dialog).getByLabelText("Extra fee 1"), "2000");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(body).toMatchObject({
        academic_year: 2,
        standard: 10,
        total_fee: "20000",
        add_ons: [{ subject: 31, amount: "2000" }],
      }),
    );
  }, 20_000); // a long form to fill: give it time when the whole suite runs in parallel

  it("asks for an amount for each extra", async () => {
    server.use(http.get(`${API}/admin/fee-structures/`, () => ok([], page(0))));
    const { user } = renderScreen(<StructuresTab />, { path: "/staff/fees?tab=structures" });
    await user.click(screen.getByRole("button", { name: "+ Add fee structure" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "+ Add optional subject fee" }));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(
      await within(dialog).findByText(/enter an amount for each extra fee/),
    ).toBeInTheDocument();
  });
});

describe("Fee structures: included subjects", () => {
  const MATH = { id: 21, name: "Mathematics", code: "MATH", is_main: true, is_active: true };
  const SCI = { id: 22, name: "Science", code: "SCI", is_main: true, is_active: true };
  const ENG = { id: 23, name: "English", code: "ENG", is_main: true, is_active: true };

  const openNew = async () => {
    server.use(
      http.get(`${API}/academics/subjects/`, () =>
        ok([ENG, { ...GUJ, is_main: false }, MATH, SCI], page(4)),
      ),
      http.get(`${API}/admin/fee-structures/`, () => ok([], page(0))),
    );
    const view = renderScreen(<StructuresTab />, { path: "/staff/fees?tab=structures" });
    await view.user.click(screen.getByRole("button", { name: "+ Add fee structure" }));
    const dialog = await screen.findByRole("dialog", { name: "Add fee structure" });
    return { ...view, dialog };
  };

  const optionalRow = async (
    user: ReturnType<typeof renderScreen>["user"],
    dialog: HTMLElement,
    n: number,
    subject: string,
  ) => {
    await user.click(within(dialog).getByRole("button", { name: "+ Add optional subject fee" }));
    const select = within(dialog).getByLabelText(`Optional subject ${n}`);
    await waitFor(() =>
      expect(within(select).getByRole("option", { name: "Gujarati" })).toBeInTheDocument(),
    );
    await user.selectOptions(select, subject);
  };

  it("starts with the main subjects; making one optional takes its amount off the standard fee", async () => {
    let body: Record<string, unknown> | undefined;
    const { user, dialog } = await openNew();
    server.use(
      http.post(`${API}/admin/fee-structures/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ id: 5 });
      }),
    );
    // The main subjects are ticked; others aren't.
    await waitFor(() => expect(within(dialog).getByLabelText("Mathematics")).toBeChecked());
    expect(within(dialog).getByLabelText("Science")).toBeChecked();
    expect(within(dialog).getByLabelText("English")).toBeChecked();
    expect(within(dialog).getByLabelText("Gujarati")).not.toBeChecked();

    const board = within(dialog).getByLabelText("Board");
    await waitFor(() =>
      expect(within(board).getByRole("option", { name: /CBSE/ })).toBeInTheDocument(),
    );
    await user.selectOptions(board, "1");
    await user.selectOptions(within(dialog).getByLabelText("Standard"), "10");
    const fee = within(dialog).getByLabelText("Standard fee (for the included subjects)");
    await user.type(fee, "20000");
    const totals = within(dialog).getByLabelText("Yearly totals");
    expect(totals).toHaveTextContent("Student taking all included subjects: ₹20,000");

    // Science becomes optional at 3000: out of the included ones, off the standard fee.
    await optionalRow(user, dialog, 1, "22");
    expect(within(dialog).getByLabelText("Science")).not.toBeChecked();
    await user.type(within(dialog).getByLabelText("Extra fee 1"), "3000");
    expect(fee).toHaveValue("17000");
    expect(totals).toHaveTextContent("Student taking all included subjects: ₹17,000");
    expect(totals).toHaveTextContent("Also taking every optional subject: ₹20,000");

    // Changing the amount keeps a student taking everything on the same total.
    await user.clear(within(dialog).getByLabelText("Extra fee 1"));
    await user.type(within(dialog).getByLabelText("Extra fee 1"), "2500");
    expect(fee).toHaveValue("17500");

    // A subject that wasn't included doesn't touch the standard fee.
    await optionalRow(user, dialog, 2, "31");
    await user.type(within(dialog).getByLabelText("Extra fee 2"), "2000");
    expect(fee).toHaveValue("17500");
    expect(totals).toHaveTextContent("Also taking every optional subject: ₹22,000");

    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toMatchObject({
      total_fee: "17500",
      add_ons: [
        { subject: 22, amount: "2500" },
        { subject: 31, amount: "2000" },
      ],
    });
    expect([...(body!.included_subjects as number[])].sort()).toEqual([21, 23]);
  }, 20_000);

  it("'Make included' puts the subject and its amount back", async () => {
    const { user, dialog } = await openNew();
    await waitFor(() => expect(within(dialog).getByLabelText("Science")).toBeChecked());
    const fee = within(dialog).getByLabelText("Standard fee (for the included subjects)");
    await user.type(fee, "20000");
    await optionalRow(user, dialog, 1, "22");
    await user.type(within(dialog).getByLabelText("Extra fee 1"), "3000");
    expect(fee).toHaveValue("17000");

    await user.click(within(dialog).getByRole("button", { name: "Make Science included" }));
    expect(fee).toHaveValue("20000");
    expect(within(dialog).getByLabelText("Science")).toBeChecked();
    expect(within(dialog).queryByLabelText("Extra fee 1")).not.toBeInTheDocument();

    // Ticking an optional subject as included does the same.
    await optionalRow(user, dialog, 1, "31");
    await user.type(within(dialog).getByLabelText("Extra fee 1"), "2000");
    await user.click(within(dialog).getByLabelText("Gujarati"));
    expect(fee).toHaveValue("22000");
    expect(within(dialog).queryByLabelText("Extra fee 1")).not.toBeInTheDocument();
  }, 20_000);

  it("shows the included subjects in the list and keeps them when editing", async () => {
    let body: Record<string, unknown> | undefined;
    server.use(
      http.get(`${API}/academics/subjects/`, () => ok([ENG, MATH, SCI], page(3))),
      http.get(`${API}/admin/fee-structures/`, () =>
        ok(
          [
            {
              id: 9,
              academic_year: 1,
              academic_year_name: "2026-27",
              board_code: "CBSE",
              standard: 10,
              standard_name: "Standard 10",
              total_fee: "18000.00",
              included_subjects: [21, 23],
              included_subject_names: ["English", "Mathematics"],
              add_ons: [],
              description: "",
              is_active: true,
            },
          ],
          page(1),
        ),
      ),
      http.patch(`${API}/admin/fee-structures/9/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({ id: 9 });
      }),
    );
    const { user } = renderScreen(<StructuresTab />, { path: "/staff/fees?tab=structures" });
    expect(await screen.findByText("English, Mathematics")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit fee structure" });
    // Science is a main subject, but this structure doesn't include it.
    await waitFor(() => expect(within(dialog).getByLabelText("Mathematics")).toBeChecked());
    expect(within(dialog).getByLabelText("Science")).not.toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toMatchObject({ total_fee: "18000", included_subjects: [21, 23] });
  });
});

describe("SubjectFeeFollowUp", () => {
  it("offers to add a started subject's fee and take off a dropped one", async () => {
    const posted: unknown[] = [];
    const onClose = vi.fn();
    server.use(
      http.get(`${API}/admin/fees/students/7/accounts/`, () =>
        ok([{ id: 5, academic_year: 1, academic_year_name: "2026-27", board: "CBSE" }]),
      ),
      http.get(`${API}/admin/fees/accounts/5/`, () =>
        ok({
          id: 5,
          board: "CBSE",
          academic_year_name: "2026-27",
          pending: "21500.00",
          entries: [
            { id: 1, entry_type: "CHARGE", amount: "20000.00", subject: null },
            { id: 2, entry_type: "CHARGE", amount: "1500.00", subject: 32, subject_name: "Hindi" },
          ],
        }),
      ),
      http.get(`${API}/admin/fee-structures/`, () =>
        ok(
          [{ id: 9, add_ons: [{ subject: 31, subject_name: "Gujarati", amount: "2000.00" }] }],
          page(1),
        ),
      ),
      http.post(`${API}/admin/fees/accounts/5/subject-fees/`, async ({ request }) => {
        posted.push(await request.json());
        return ok({ id: 5 });
      }),
    );
    const { user } = renderScreen(
      <SubjectFeeFollowUp
        studentId={7}
        standardId={10}
        added={[{ id: 31, name: "Gujarati" }]}
        dropped={[{ id: 32, name: "Hindi" }]}
        onClose={onClose}
      />,
    );

    // The dialog shows a loading state first, then the choices.
    expect(await screen.findByLabelText("Gujarati amount")).toHaveValue("2000");
    expect(screen.getByLabelText("Hindi amount")).toHaveValue("1500");
    await user.click(screen.getByRole("button", { name: "Update fees" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(posted).toEqual([
      { subject: 31, action: "ADD", amount: "2000" },
      { subject: 32, action: "REMOVE", amount: "1500" },
    ]);
  });

  it("closes without asking when no optional-subject fee is affected", async () => {
    const onClose = vi.fn();
    server.use(
      http.get(`${API}/admin/fees/students/7/accounts/`, () =>
        ok([{ id: 5, academic_year: 1, academic_year_name: "2026-27", board: "CBSE" }]),
      ),
      http.get(`${API}/admin/fees/accounts/5/`, () => ok({ id: 5, entries: [] })),
      http.get(`${API}/admin/fee-structures/`, () => ok([{ id: 9, add_ons: [] }], page(1))),
    );
    renderScreen(
      <SubjectFeeFollowUp
        studentId={7}
        standardId={10}
        added={[{ id: 33, name: "Science" }]}
        dropped={[]}
        onClose={onClose}
      />,
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(
      screen.queryByRole("dialog", { name: "Update this year's fees?" }),
    ).not.toBeInTheDocument();
  });
});

describe("entryLabel", () => {
  it("names optional subject lines", () => {
    expect(entryLabel({ entry_type: "CHARGE", subject_name: "Gujarati" })).toBe(
      "Gujarati (optional subject)",
    );
    expect(entryLabel({ entry_type: "ADJUSTMENT", subject_name: "Hindi" })).toBe(
      "Hindi fee taken off",
    );
    expect(entryLabel({ entry_type: "PAYMENT" })).toBe("Payment");
  });
});
