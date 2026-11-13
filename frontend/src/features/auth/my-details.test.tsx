import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { API, http, makeUser, ok, renderScreen, setupMockServer } from "@/test/render";

import { MyDetailsCard } from "./components/MyDetailsCard";

const server = setupMockServer();

describe("MyDetailsCard", () => {
  it("edits my own name", async () => {
    let body: unknown;
    const me = makeUser({ first_name: "Het", last_name: "Shukla" });
    server.use(
      http.patch(`${API}/auth/me/`, async ({ request }) => {
        body = await request.json();
        return ok({ ...me, first_name: "Het", last_name: "S." });
      }),
    );
    const { user } = renderScreen(<MyDetailsCard user={me} />);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit name" });
    const last = within(dialog).getByLabelText("Last name");
    await user.clear(last);
    await user.type(last, "S.");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(body).toEqual({ first_name: "Het", last_name: "S." }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("changes email in two steps: the new address, then the code sent to it", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const me = makeUser({ email: "old@example.com", phone: null });
    server.use(
      http.post(`${API}/auth/me/contact/`, async ({ request }) => {
        calls.push({ url: "request", body: await request.json() });
        return ok({ sent_to: "n***@example.com", expires_in_seconds: 600 });
      }),
      http.post(`${API}/auth/me/contact/verify/`, async ({ request }) => {
        calls.push({ url: "verify", body: await request.json() });
        return ok({ ...me, email: "new@example.com" });
      }),
    );
    const { user } = renderScreen(<MyDetailsCard user={me} />);

    // With only an email, it can't be removed (they'd have no way to log in).
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Change" })[0]!);
    const dialog = await screen.findByRole("dialog", { name: "Change email" });
    await user.type(within(dialog).getByLabelText("New email"), "new@example.com");
    await user.click(within(dialog).getByRole("button", { name: "Send code" }));

    expect(await within(dialog).findByText("n***@example.com")).toBeInTheDocument();
    await user.keyboard("123456");
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[0]?.body).toEqual({ channel: "EMAIL", identifier: "new@example.com" });
    expect(calls[1]?.body).toEqual({
      channel: "EMAIL",
      identifier: "new@example.com",
      code: "123456",
    });
  });

  it("unlinks Google after confirming", async () => {
    let unlinked = false;
    const me = makeUser({ google_linked: true });
    server.use(
      http.post(`${API}/auth/google/unlink/`, () => {
        unlinked = true;
        return ok({ ...me, google_linked: false });
      }),
    );
    const { user } = renderScreen(<MyDetailsCard user={me} />);

    await user.click(screen.getByRole("button", { name: "Unlink" }));
    const dialog = await screen.findByRole("dialog", { name: "Unlink Google?" });
    await user.click(within(dialog).getByRole("button", { name: "Unlink" }));
    await waitFor(() => expect(unlinked).toBe(true));
  });
});
