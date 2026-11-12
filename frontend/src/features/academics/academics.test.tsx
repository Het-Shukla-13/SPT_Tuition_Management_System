import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { API, fail, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { AcademicsPage } from "./pages/AcademicsPage";

const server = setupMockServer();

const CBSE = { id: 1, code: "CBSE", name: "Central Board", is_active: true };
const YEAR = {
  id: 9,
  board: 1,
  board_code: "CBSE",
  name: "2026-27",
  start_date: "2026-04-01",
  end_date: "2027-03-31",
  is_current: true,
  is_active: true,
};

function mockLists() {
  server.use(
    http.get(`${API}/academics/academic-years/`, () => ok([YEAR], page(1))),
    http.get(`${API}/academics/boards/`, () => ok([CBSE], page(1))),
  );
}

describe("AcademicsPage", () => {
  it("opens on academic years and marks the current one", async () => {
    mockLists();
    renderScreen(<AcademicsPage />, { path: "/staff/academics", route: "/staff/academics" });
    expect(await screen.findByText("2026-27")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("switching tabs uses the same screen for another type, kept in the URL", async () => {
    mockLists();
    const { user, search } = renderScreen(<AcademicsPage />, { path: "/staff/academics" });
    await user.click(screen.getByRole("button", { name: "Boards" }));
    expect(await screen.findByText("Central Board")).toBeInTheDocument();
    await waitFor(() => expect(search()).toContain("tab=boards"));
  });

  it("adds a board from the generic form", async () => {
    mockLists();
    let body: unknown;
    server.use(
      http.post(`${API}/academics/boards/`, async ({ request }) => {
        body = await request.json();
        return ok({ ...CBSE, id: 2, code: "IB", name: "International" });
      }),
    );
    const { user } = renderScreen(<AcademicsPage />, {
      path: "/staff/academics?tab=boards",
      route: "/staff/academics",
    });
    await user.click(await screen.findByRole("button", { name: "+ Add board" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "IB");
    await user.type(within(dialog).getByLabelText("Name"), "International");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(body).toEqual({ code: "IB", name: "International" });
  });

  it("checks required fields before sending, and shows server errors per field", async () => {
    mockLists();
    server.use(
      http.post(`${API}/academics/boards/`, () =>
        fail(400, "VALIDATION_ERROR", "Validation failed.", {
          code: ["A board with this code already exists."],
        }),
      ),
    );
    const { user } = renderScreen(<AcademicsPage />, {
      path: "/staff/academics?tab=boards",
      route: "/staff/academics",
    });
    await user.click(await screen.findByRole("button", { name: "+ Add board" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(within(dialog).getByText("Enter code.")).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Code"), "CBSE");
    await user.type(within(dialog).getByLabelText("Name"), "Again");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(
      await within(dialog).findByText("A board with this code already exists."),
    ).toBeInTheDocument();
  });

  it("deactivates instead of deleting", async () => {
    mockLists();
    let body: unknown;
    server.use(
      http.patch(`${API}/academics/boards/1/`, async ({ request }) => {
        body = await request.json();
        return ok({ ...CBSE, is_active: false });
      }),
    );
    const { user } = renderScreen(<AcademicsPage />, {
      path: "/staff/academics?tab=boards",
      route: "/staff/academics",
    });
    await user.click(await screen.findByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(body).toEqual({ is_active: false }));
  });

  it("an academic year's board can't be changed after creation", async () => {
    mockLists();
    const { user } = renderScreen(<AcademicsPage />, {
      path: "/staff/academics",
      route: "/staff/academics",
    });
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Board")).toBeDisabled();
    expect(within(dialog).getByText("Can't be changed after it's created.")).toBeInTheDocument();
  });
});
