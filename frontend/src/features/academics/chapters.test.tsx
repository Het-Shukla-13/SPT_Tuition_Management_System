import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { API, http, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { AcademicsPage } from "./pages/AcademicsPage";

const server = setupMockServer();

const LIGHT = {
  id: 7,
  standard: 10,
  standard_name: "Standard 10",
  subject: 22,
  subject_name: "Science",
  name: "Light",
  is_active: true,
};

describe("Chapters are topics of a standard + subject", () => {
  it("lists and adds them without a board or a chapter number", async () => {
    let body: unknown;
    server.use(
      http.get(`${API}/academics/chapters/`, () => ok([LIGHT], page(1))),
      http.get(`${API}/academics/standards/`, () =>
        ok([{ id: 10, name: "Standard 10", level: 10, is_active: true }], page(1)),
      ),
      http.get(`${API}/academics/subjects/`, () =>
        ok([{ id: 22, name: "Science", code: "SCI", is_active: true }], page(1)),
      ),
      http.post(`${API}/academics/chapters/`, async ({ request }) => {
        body = await request.json();
        return ok({ ...LIGHT, id: 8, name: "Electricity" });
      }),
    );
    const { user } = renderScreen(<AcademicsPage />, {
      path: "/staff/academics?tab=chapters",
      route: "/staff/academics",
    });

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Chapter" })).toBeInTheDocument();
    expect(within(table).queryByRole("columnheader", { name: "No." })).not.toBeInTheDocument();
    expect(await within(table).findByText("Light")).toBeInTheDocument();
    expect(screen.queryByLabelText("Board")).not.toBeInTheDocument(); // no board filter

    await user.click(screen.getByRole("button", { name: "+ Add chapter" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByLabelText("Board")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Chapter no.")).not.toBeInTheDocument();
    const standard = within(dialog).getByLabelText("Standard");
    await waitFor(() =>
      expect(within(standard).getByRole("option", { name: "Standard 10" })).toBeInTheDocument(),
    );
    await user.selectOptions(standard, "10");
    await user.selectOptions(within(dialog).getByLabelText("Subject"), "22");
    await user.type(within(dialog).getByLabelText("Chapter name"), "Electricity");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(body).toEqual({ standard: 10, subject: 22, name: "Electricity" }));
  });
});
