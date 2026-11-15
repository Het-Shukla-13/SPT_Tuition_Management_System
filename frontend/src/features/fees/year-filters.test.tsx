import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { AccountsTab } from "./components/AccountsTab";
import { RolloverTab } from "./components/RolloverTab";
import { laterYears, yearNameOptions } from "./years";

const server = setupMockServer();

const YEARS = [
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
    board: 1,
    board_code: "CBSE",
    name: "2025-26",
    start_date: "2025-04-01",
    is_current: false,
    is_active: true,
  },
  {
    id: 4,
    board: 1,
    board_code: "CBSE",
    name: "2027-28",
    start_date: "2027-04-01",
    is_current: false,
    is_active: true,
  },
];

beforeEach(() => {
  server.use(
    http.get(`${API}/academics/academic-years/`, () => ok(YEARS, page(YEARS.length))),
    http.get(`${API}/academics/boards/`, () =>
      ok(
        [
          { id: 1, code: "CBSE", name: "Central Board", is_active: true },
          { id: 2, code: "GSEB", name: "Gujarat Board", is_active: true },
        ],
        page(2),
      ),
    ),
    http.get(`${API}/academics/standards/`, () => ok([], page(0))),
  );
});

describe("Accounts: year and board are independent", () => {
  it("a year on its own covers every board; each year name appears once", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/fees/accounts/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok([], page(0));
      }),
    );
    const { user, search } = renderScreen(<AccountsTab />, { path: "/staff/fees" });

    const year = await screen.findByLabelText("Academic year");
    await waitFor(() => expect(within(year).getAllByRole("option")).toHaveLength(4));
    expect(
      within(year)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["All years", "2027-28", "2026-27", "2025-26"]);

    await user.selectOptions(year, "2026-27");
    await waitFor(() => expect(seen.at(-1)?.get("academic_year__name")).toBe("2026-27"));
    expect(seen.at(-1)?.get("academic_year__board")).toBeNull();
    expect(search()).toContain("academic_year__name=2026-27");

    // Adding a board narrows it to that board's 2026-27.
    await user.selectOptions(screen.getByLabelText("Board"), "2");
    await waitFor(() => expect(seen.at(-1)?.get("academic_year__board")).toBe("2"));
    expect(seen.at(-1)?.get("academic_year__name")).toBe("2026-27");
  });
});

describe("Rollover: only years after the board's current one", () => {
  it("offers the next year by plain name, and explains when there isn't one", async () => {
    const { user } = renderScreen(<RolloverTab />, { path: "/staff/fees?tab=rollover" });
    const board = await screen.findByLabelText("Board");
    await waitFor(() =>
      expect(within(board).getByRole("option", { name: /CBSE/ })).toBeInTheDocument(),
    );

    await user.selectOptions(board, "1");
    const year = screen.getByLabelText("Move into year");
    expect(
      within(year)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Choose…", "2027-28"]);

    await user.selectOptions(board, "2");
    expect(screen.getByLabelText("Move into year")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "There's no year after 2026-27 for this board yet.",
    );
    expect(screen.getByRole("link", { name: "Create the next academic year" })).toHaveAttribute(
      "href",
      "/staff/academics?tab=academic-years",
    );
  });
});

describe("year helpers", () => {
  const years = YEARS.map((y) => ({ ...y }));
  it("lists names once, newest first, optionally for one board", () => {
    expect(yearNameOptions(years).map((o) => o.value)).toEqual(["2027-28", "2026-27", "2025-26"]);
    expect(yearNameOptions(years, "2").map((o) => o.value)).toEqual(["2026-27"]);
  });
  it("later years are only those after the current one", () => {
    expect(laterYears(years, "1").map((y) => y.name)).toEqual(["2027-28"]);
    expect(laterYears(years, "2")).toEqual([]);
  });
});
