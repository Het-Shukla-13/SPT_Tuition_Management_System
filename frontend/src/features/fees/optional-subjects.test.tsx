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
          { id: 1, board: 1, board_code: "CBSE", name: "2026-27", is_active: true },
          { id: 2, board: 2, board_code: "GSEB", name: "2026-27", is_active: true },
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
  it("names the board in the year dropdown and saves the extras", async () => {
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
    // Same year name on two boards: the board makes them tell-apart-able.
    expect(await within(year).findByRole("option", { name: "GSEB 2026-27" })).toBeInTheDocument();
    await user.selectOptions(year, "2");
    await user.selectOptions(within(dialog).getByLabelText("Standard"), "10");
    await user.type(within(dialog).getByLabelText("Yearly fee (₹)"), "20000");

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
  });

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
