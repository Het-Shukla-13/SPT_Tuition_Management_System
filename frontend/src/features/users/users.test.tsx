import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { API, fail, http, makeUser, ok, page, renderScreen, setupMockServer } from "@/test/render";

import { UserDetailPage } from "./pages/UserDetailPage";
import { UsersPage } from "./pages/UsersPage";

const server = setupMockServer();

const TEACHER = {
  id: 5,
  first_name: "Mehul",
  last_name: "Pandya",
  email: "mehul@example.com",
  phone: "+919876543210",
  role: "TEACHER",
  is_active: true,
  is_superuser: false,
  invite_accepted: false,
  last_login: null,
  email_verified_at: null,
  phone_verified_at: null,
  activated_at: null,
  created_at: "2026-11-01T10:00:00+05:30",
};

describe("UsersPage", () => {
  it("lists users, and filters through the URL and the API", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/users/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return ok([TEACHER], page(1));
      }),
    );
    const { user, search } = renderScreen(<UsersPage />, {
      path: "/staff/users",
      route: "/staff/users",
    });

    expect(await screen.findByRole("link", { name: /Mehul Pandya/ })).toBeInTheDocument();
    expect(screen.getByText("Invited")).toBeInTheDocument();
    expect(seen[0]?.get("is_active")).toBe("true"); // active users by default

    await user.selectOptions(screen.getByLabelText("Role"), "TEACHER");
    await waitFor(() => expect(seen.at(-1)?.get("role")).toBe("TEACHER"));
    expect(search()).toContain("role=TEACHER");
  });

  it("invite: an admin can't pick Admin; the owner can", async () => {
    server.use(http.get(`${API}/admin/users/`, () => ok([], page(0))));
    const { user } = renderScreen(<UsersPage />, { path: "/staff/users", route: "/staff/users" });
    await user.click(screen.getByRole("button", { name: "+ Invite staff" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("option", { name: "Admin" })).not.toBeInTheDocument();
    expect(within(dialog).getByText("Only the owner can invite admins.")).toBeInTheDocument();
  });

  it("invite sends the form and closes", async () => {
    let body: unknown;
    server.use(
      http.get(`${API}/admin/users/`, () => ok([], page(0))),
      http.post(`${API}/admin/users/`, async ({ request }) => {
        body = await request.json();
        return ok({ user: TEACHER, invite_sent: { email: true } });
      }),
    );
    const { user } = renderScreen(<UsersPage />, {
      path: "/staff/users",
      route: "/staff/users",
      me: makeUser({ is_owner: true }),
    });
    await user.click(screen.getByRole("button", { name: "+ Invite staff" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Role"), "ADMIN");
    await user.type(within(dialog).getByLabelText("First name"), "Nisha");
    await user.type(within(dialog).getByLabelText("Last name"), "Vyas");
    await user.type(within(dialog).getByLabelText("Email"), "nisha@example.com");
    await user.click(within(dialog).getByRole("button", { name: "Send invite" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(body).toEqual({
      role: "ADMIN",
      first_name: "Nisha",
      last_name: "Vyas",
      email: "nisha@example.com",
    });
  });

  it("invite shows the server's field errors", async () => {
    server.use(
      http.get(`${API}/admin/users/`, () => ok([], page(0))),
      http.post(`${API}/admin/users/`, () =>
        fail(409, "CONTACT_IN_USE", "This email/phone is already used by another account."),
      ),
    );
    const { user } = renderScreen(<UsersPage />, { path: "/staff/users", route: "/staff/users" });
    await user.click(screen.getByRole("button", { name: "+ Invite staff" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("First name"), "A");
    await user.type(within(dialog).getByLabelText("Last name"), "B");
    await user.type(within(dialog).getByLabelText("Email"), "taken@example.com");
    await user.click(within(dialog).getByRole("button", { name: "Send invite" }));
    expect(
      await screen.findByText("This email/phone is already used by another account."),
    ).toBeInTheDocument();
  });
});

describe("UserDetailPage", () => {
  const renderDetail = (me = makeUser()) =>
    renderScreen(<UserDetailPage />, { path: "/staff/users/5", route: "/staff/users/:id", me });

  it("deactivates after confirming", async () => {
    let called = false;
    server.use(
      http.get(`${API}/admin/users/5/`, () => ok(TEACHER)),
      http.post(`${API}/admin/users/5/deactivate/`, () => {
        called = true;
        return ok({ ...TEACHER, is_active: false });
      }),
    );
    const { user } = renderDetail();
    await user.click(await screen.findByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(called).toBe(true));
  });

  it("only the owner sees 'Change role'; nobody manages themselves", async () => {
    server.use(http.get(`${API}/admin/users/5/`, () => ok(TEACHER)));
    renderDetail();
    expect(await screen.findByRole("button", { name: "Resend" })).toBeInTheDocument();
    expect(screen.queryByText("Change role")).not.toBeInTheDocument();
  });

  it("the owner can change roles", async () => {
    server.use(http.get(`${API}/admin/users/5/`, () => ok(TEACHER)));
    renderDetail(makeUser({ is_owner: true }));
    expect(await screen.findByText("Change role")).toBeInTheDocument();
  });

  it("an admin viewing another admin gets no actions (owner only)", async () => {
    server.use(http.get(`${API}/admin/users/5/`, () => ok({ ...TEACHER, role: "ADMIN" })));
    renderDetail();
    await screen.findByRole("heading", { name: "Mehul Pandya" });
    expect(screen.queryByRole("heading", { name: "Actions" })).not.toBeInTheDocument();
  });

  it("viewing yourself shows a pointer to My account instead of actions", async () => {
    server.use(http.get(`${API}/admin/users/5/`, () => ok({ ...TEACHER, id: 5 })));
    renderDetail(makeUser({ id: 5 }));
    expect(await screen.findByText(/This is you/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Actions" })).not.toBeInTheDocument();
  });
});
