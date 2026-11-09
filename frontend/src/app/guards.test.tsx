import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { ME_KEY } from "@/features/auth/session";
import type { User } from "@/lib/api/types";

import { RequireAuth } from "./guards";

function user(role: User["role"]): User {
  return { id: 1, first_name: "Test", last_name: "User", role } as User;
}

function LoginProbe() {
  const location = useLocation();
  return <p>login page {location.search}</p>;
}

function renderAt(path: string, me: User | null) {
  const queryClient = new QueryClient();
  queryClient.setQueryData(ME_KEY, me);
  const router = createMemoryRouter(
    [
      { path: "/login", element: <LoginProbe /> },
      {
        path: "/staff",
        element: <RequireAuth roles={["ADMIN", "TEACHER"]} />,
        children: [
          { index: true, element: <p>staff home</p> },
          {
            element: <RequireAuth roles={["ADMIN"]} />,
            children: [{ path: "fees", element: <p>fees page</p> }],
          },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("RequireAuth", () => {
  it("sends logged-out visitors to login and remembers where they were going", () => {
    renderAt("/staff/fees?page=2", null);
    expect(screen.getByText(/login page/)).toHaveTextContent(
      `?next=${encodeURIComponent("/staff/fees?page=2")}`,
    );
  });

  it("lets the right role in", () => {
    renderAt("/staff/fees", user("ADMIN"));
    expect(screen.getByText("fees page")).toBeInTheDocument();
  });

  it("shows 'not allowed' (not a blank page) to a teacher on an admin page", () => {
    renderAt("/staff/fees", user("TEACHER"));
    expect(screen.getByRole("heading", { name: /isn't for your account/ })).toBeInTheDocument();
    expect(screen.queryByText("fees page")).not.toBeInTheDocument();
  });

  it("keeps parents out of the staff area", () => {
    renderAt("/staff", user("PORTAL"));
    expect(screen.getByRole("link", { name: "Go to my home" })).toHaveAttribute("href", "/portal");
  });
});
