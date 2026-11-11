import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as mock, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";

import { session } from "@/lib/api/session";

import { LoginPage } from "./pages/LoginPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { safeNext } from "./redirect";
import { ME_KEY } from "./session";

const BASE = `${window.location.origin}/api/v1`;
const USER = {
  id: 7,
  first_name: "Kavita",
  last_name: "Shah",
  role: "PORTAL",
  email: "kavita@example.com",
};
const ok = (data: unknown) =>
  HttpResponse.json({
    success: true,
    message: "OK",
    data,
    errors: null,
    error_code: null,
    meta: null,
  });
const fail = (status: number, code: string, message: string, errors: unknown = null) =>
  HttpResponse.json(
    { success: false, message, data: null, errors, error_code: code, meta: null },
    { status },
  );
const authenticated = { status: "AUTHENTICATED", access: "access-1", user: USER };
const codeRequired = {
  status: "OTP_REQUIRED",
  email: "k****a@example.com",
  login_ticket: "ticket-1",
  expires_in_seconds: 300,
  resend_after_seconds: 60,
};

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => session.clear(null, false));

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ME_KEY, null); // logged out
  const router = createMemoryRouter(
    [
      { path: "/login", element: <LoginPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "/portal", element: <p>portal home</p> },
      { path: "/portal/fees", element: <p>fees page</p> },
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

async function fillLogin(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email"), "kavita@example.com");
  await user.type(screen.getByLabelText("Password"), "Chalk-and-board-2026");
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

describe("LoginPage", () => {
  it("trusted device: password logs straight in and goes home", async () => {
    let body: unknown;
    server.use(
      mock.post(`${BASE}/auth/login/`, async ({ request }) => {
        body = await request.json();
        return ok(authenticated);
      }),
    );
    const { user } = renderAt("/login");
    await fillLogin(user);

    expect(await screen.findByText("portal home")).toBeInTheDocument();
    expect(body).toEqual({ email: "kavita@example.com", password: "Chalk-and-board-2026" });
    expect(session.getAccessToken()).toBe("access-1");
  });

  it("new device: asks for the emailed code, sends it with the ticket, then honours ?next", async () => {
    let verifyBody: unknown;
    server.use(
      mock.post(`${BASE}/auth/login/`, () => ok(codeRequired)),
      mock.post(`${BASE}/auth/login/verify/`, async ({ request }) => {
        verifyBody = await request.json();
        return ok(authenticated);
      }),
    );
    const { user } = renderAt(`/login?next=${encodeURIComponent("/portal/fees")}`);
    await fillLogin(user);

    expect(await screen.findByRole("heading", { name: "Enter your code" })).toBeInTheDocument();
    expect(screen.getByText("k****a@example.com")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Digit 1"));
    await user.paste("482913");
    await user.click(screen.getByRole("button", { name: "Verify & log in" }));

    expect(await screen.findByText("fees page")).toBeInTheDocument();
    expect(verifyBody).toEqual({ login_ticket: "ticket-1", code: "482913" });
  });

  it("wrong password: shows the server's message and stays on the form", async () => {
    server.use(
      mock.post(`${BASE}/auth/login/`, () =>
        fail(400, "INVALID_CREDENTIALS", "Email or password is incorrect."),
      ),
    );
    const { user } = renderAt("/login");
    await fillLogin(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("lockout: shows a countdown and disables the button", async () => {
    server.use(
      mock.post(`${BASE}/auth/login/`, () =>
        fail(429, "LOGIN_LOCKED", "Too many wrong passwords.", { retry_after_seconds: 600 }),
      ),
    );
    const { user } = renderAt("/login");
    await fillLogin(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 10:00");
    expect(screen.getByRole("button", { name: /Try again in/ })).toBeDisabled();
  });

  it("validates the form before calling the server", async () => {
    const { user } = renderAt("/login");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  });

  it("the 'first time / forgot' link carries the typed email", async () => {
    const { user, router } = renderAt("/login");
    await user.type(screen.getByLabelText("Email"), "kavita@example.com");
    await user.click(screen.getByRole("link", { name: /First time here/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/reset-password"));
    expect(screen.getByLabelText("Email")).toHaveValue("kavita@example.com");
  });
});

describe("ResetPasswordPage", () => {
  it("email → code + new password → logged in", async () => {
    let confirmBody: unknown;
    server.use(
      mock.post(`${BASE}/auth/password/reset/`, () => ok({ status: "CODE_SENT" })),
      mock.post(`${BASE}/auth/password/reset/confirm/`, async ({ request }) => {
        confirmBody = await request.json();
        return ok(authenticated);
      }),
    );
    const { user } = renderAt("/reset-password?email=kavita%40example.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(
      await screen.findByRole("heading", { name: "Choose your password" }),
    ).toBeInTheDocument();
    await user.click(screen.getByLabelText("Digit 1"));
    await user.paste("123456");
    await user.type(screen.getByLabelText("New password"), "Sai-Tuitions-Rocks-42");
    await user.type(screen.getByLabelText("Type it again"), "Sai-Tuitions-Rocks-42");
    await user.click(screen.getByRole("button", { name: /Save password/ }));

    expect(await screen.findByText("portal home")).toBeInTheDocument();
    expect(confirmBody).toEqual({
      email: "kavita@example.com",
      code: "123456",
      new_password: "Sai-Tuitions-Rocks-42",
    });
  });

  it("shows the server's weak-password reasons next to the field", async () => {
    server.use(
      mock.post(`${BASE}/auth/password/reset/`, () => ok({ status: "CODE_SENT" })),
      mock.post(`${BASE}/auth/password/reset/confirm/`, () =>
        fail(400, "VALIDATION_ERROR", "Validation failed.", {
          new_password: ["This password is too common."],
        }),
      ),
    );
    const { user } = renderAt("/reset-password?email=kavita%40example.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByRole("heading", { name: "Choose your password" });
    await user.click(screen.getByLabelText("Digit 1"));
    await user.paste("123456");
    await user.type(screen.getByLabelText("New password"), "password123");
    await user.type(screen.getByLabelText("Type it again"), "password123");
    await user.click(screen.getByRole("button", { name: /Save password/ }));

    expect(await screen.findByText("This password is too common.")).toBeInTheDocument();
  });

  it("catches mismatched passwords before calling the server", async () => {
    server.use(mock.post(`${BASE}/auth/password/reset/`, () => ok({ status: "CODE_SENT" })));
    const { user } = renderAt("/reset-password?email=kavita%40example.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByRole("heading", { name: "Choose your password" });
    await user.click(screen.getByLabelText("Digit 1"));
    await user.paste("123456");
    await user.type(screen.getByLabelText("New password"), "Sai-Tuitions-Rocks-42");
    await user.type(screen.getByLabelText("Type it again"), "something-else-42");
    await user.click(screen.getByRole("button", { name: /Save password/ }));

    expect(await screen.findByText("The passwords don't match.")).toBeInTheDocument();
  });
});

describe("safeNext", () => {
  it("accepts only same-site paths", () => {
    expect(safeNext("/portal/fees?x=1")).toBe("/portal/fees?x=1");
    expect(safeNext("//evil.com")).toBeNull();
    expect(safeNext("https://evil.com")).toBeNull();
    expect(safeNext("/\\evil.com")).toBeNull();
    expect(safeNext("/login")).toBeNull();
    expect(safeNext(null)).toBeNull();
  });
});
