import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";

import { session } from "@/lib/api/session";
import { API, fail, http, makeUser, ok, renderScreen, setupMockServer } from "@/test/render";

import { SetFirstPasswordCard } from "./components/SetFirstPasswordCard";
import { LoginPage } from "./pages/LoginPage";
import { SetPasswordPage } from "./pages/SetPasswordPage";
import { ME_KEY } from "./session";

const server = setupMockServer();
const USER = {
  id: 7,
  first_name: "Kavita",
  last_name: "Shah",
  role: "PORTAL",
  email: "kavita@example.com",
};

beforeEach(() => session.clear(null, false));

function renderAt(path: string, methods = { email: true, phone: false, google: false }) {
  server.use(http.get(`${API}/auth/methods/`, () => ok(methods)));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ME_KEY, null); // logged out
  const router = createMemoryRouter(
    [
      { path: "/login", element: <LoginPage /> },
      { path: "/set-password", element: <SetPasswordPage /> },
      { path: "/reset-password", element: <p>reset page</p> },
      { path: "/portal", element: <p>portal home</p> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, user: userEvent.setup() };
}

describe("Login method choice", () => {
  it("offers email, and phone only when SMS is set up", async () => {
    renderAt("/login");
    expect(await screen.findByRole("button", { name: "Continue with email" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue with phone" })).not.toBeInTheDocument();
    // Footer links on every login screen.
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(screen.getByRole("link", { name: "Terms of Use" })).toHaveAttribute("href", "/terms");
  });

  it("logs in by phone with an SMS code", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/auth/otp/request/`, async ({ request }) => {
        bodies.push(await request.json());
        return ok({ expires_in_seconds: 300, resend_after_seconds: 60 });
      }),
      http.post(`${API}/auth/otp/verify/`, async ({ request }) => {
        bodies.push(await request.json());
        return ok({ access: "access-1", user: USER });
      }),
    );
    const { user, router } = renderAt("/login", { email: true, phone: true, google: false });

    await user.click(await screen.findByRole("button", { name: "Continue with phone" }));
    await user.type(screen.getByLabelText("Mobile number"), "98765 43210");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByRole("heading", { name: "Enter your code" })).toBeInTheDocument();
    await user.keyboard("123456");
    await user.click(screen.getByRole("button", { name: "Verify & log in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/portal"));
    expect(bodies).toEqual([
      { channel: "PHONE", identifier: "98765 43210", purpose: "LOGIN" },
      { channel: "PHONE", identifier: "98765 43210", purpose: "LOGIN", code: "123456" },
    ]);
  });

  it("after the invite link: email form, pre-filled, with an 'Invitation accepted' note", async () => {
    renderAt("/login?invited=1&email=meera%40example.com");
    expect(await screen.findByText("Invitation accepted.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("meera@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});

describe("SetPasswordPage (invite link)", () => {
  it("greets them, saves the password and sends them to log in", async () => {
    let accepted: unknown;
    server.use(
      http.post(`${API}/auth/invite/check/`, () =>
        ok({ first_name: "Meera", email: "meera@example.com" }),
      ),
      http.post(`${API}/auth/invite/accept/`, async ({ request }) => {
        accepted = await request.json();
        return ok({ first_name: "Meera", email: "meera@example.com" });
      }),
    );
    const { user, router } = renderAt("/set-password?token=tok-123");

    expect(await screen.findByRole("heading", { name: "Welcome, Meera!" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("New password"), "Chalk-and-board-2026");
    await user.type(screen.getByLabelText("Type it again"), "Chalk-and-board-2026");
    await user.click(screen.getByRole("button", { name: "Set password" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.search).toBe("?invited=1&email=meera%40example.com");
    expect(accepted).toEqual({ token: "tok-123", new_password: "Chalk-and-board-2026" });
    expect(await screen.findByText("Invitation accepted.")).toBeInTheDocument();
  });

  it("explains an expired or used link and offers the code route", async () => {
    server.use(
      http.post(`${API}/auth/invite/check/`, () =>
        fail(400, "INVITE_LINK_INVALID", "This invite link didn't work."),
      ),
    );
    renderAt("/set-password?token=old");
    expect(
      await screen.findByRole("heading", { name: "This invite link didn't work" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set my password with a code" })).toHaveAttribute(
      "href",
      "/reset-password",
    );
  });
});

describe("SetFirstPasswordCard", () => {
  it("lets a Google-only user set a password with a code to their email", async () => {
    const calls: unknown[] = [];
    server.use(
      http.post(`${API}/auth/password/reset/`, async ({ request }) => {
        calls.push(await request.json());
        return ok({
          status: "OTP_REQUIRED",
          email: "k***@example.com",
          expires_in_seconds: 300,
          resend_after_seconds: 60,
        });
      }),
      http.post(`${API}/auth/password/reset/confirm/`, async ({ request }) => {
        calls.push(await request.json());
        return ok({ status: "AUTHENTICATED", access: "access-2", user: USER });
      }),
    );
    const me = makeUser({ email: "kavita@example.com", google_linked: true, has_password: false });
    const { user } = renderScreen(<SetFirstPasswordCard user={me} />);

    expect(screen.getByText(/you log in with Google/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByText(/We sent a 6-digit code/)).toBeInTheDocument();
    await user.keyboard("123456");
    await user.type(screen.getByLabelText("New password"), "Chalk-and-board-2026");
    await user.type(screen.getByLabelText("Type it again"), "Chalk-and-board-2026");
    await user.click(screen.getByRole("button", { name: "Set password" }));

    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[0]).toEqual({ email: "kavita@example.com" });
    expect(calls[1]).toEqual({
      email: "kavita@example.com",
      code: "123456",
      new_password: "Chalk-and-board-2026",
    });
    await waitFor(() => expect(session.getAccessToken()).toBe("access-2"));
  });

  it("phone-only users are told they don't need one", () => {
    renderScreen(
      <SetFirstPasswordCard
        user={makeUser({ email: null, phone: "+919876543210", has_password: false })}
      />,
    );
    expect(screen.getByText(/You log in with a code sent to your phone/)).toBeInTheDocument();
  });
});
