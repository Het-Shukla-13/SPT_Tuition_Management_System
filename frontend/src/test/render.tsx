/**
 * Shared test helpers: render screens with the real providers (router, data
 * cache, URL state, logged-in user) against an MSW mock API.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { createMemoryRouter, type RouteObject, RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { afterAll, afterEach, beforeAll } from "vitest";

import { CurrentUserContext } from "@/features/auth/session";
import type { User } from "@/lib/api/types";

export const API = `${window.location.origin}/api/v1`;

export const ok = (data: unknown, meta: unknown = null) =>
  HttpResponse.json({ success: true, message: "OK", data, errors: null, error_code: null, meta });

export const fail = (status: number, code: string, message: string, errors: unknown = null) =>
  HttpResponse.json(
    { success: false, message, data: null, errors, error_code: code, meta: null },
    { status },
  );

export const page = (count: number, pageNo = 1) => ({
  page: pageNo,
  page_size: 20,
  total_count: count,
  total_pages: Math.max(1, Math.ceil(count / 20)),
  has_next: pageNo * 20 < count,
  has_previous: pageNo > 1,
});

export { http };

/** One MSW server per test file; unhandled requests fail the test. */
export function setupMockServer() {
  const server = setupServer();
  beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
  return server;
}

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    first_name: "Office",
    last_name: "Admin",
    email: "admin@example.com",
    phone: null,
    role: "ADMIN",
    is_owner: false,
    google_linked: false,
    ...overrides,
  } as User;
}

/**
 * Render `element` at `path` (pattern `route`) as `me`.
 * URL query state goes through nuqs' testing adapter (in memory, isolated per
 * test); `search()` returns the latest query string the screen wrote.
 */
export function renderScreen(
  element: ReactNode,
  {
    path = "/",
    route = path.split("?")[0]!,
    me = makeUser(),
    extraRoutes = [],
  }: {
    path?: string;
    route?: string;
    me?: User;
    extraRoutes?: RouteObject[];
  } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const initialSearch = path.includes("?") ? path.slice(path.indexOf("?")) : "";
  let latest = initialSearch.replace(/^\?/, "");
  const router = createMemoryRouter(
    [
      {
        path: route,
        element: (
          <CurrentUserContext.Provider value={me}>
            <NuqsTestingAdapter
              searchParams={initialSearch}
              hasMemory
              onUrlUpdate={(event) => {
                latest = event.queryString.replace(/^\?/, "");
              }}
            >
              {element}
            </NuqsTestingAdapter>
          </CurrentUserContext.Provider>
        ),
      },
      ...extraRoutes,
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>,
  );
  return { router, user: userEvent.setup(), queryClient, search: () => latest };
}
