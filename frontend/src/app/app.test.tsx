import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ME_KEY } from "@/features/auth/session";
import { API, http, makeUser, ok, setupMockServer } from "@/test/render";

import { Providers } from "./providers";
import { RouteError } from "./RouteError";
import { routes } from "./router";
import { isStaleBuildError } from "./staleBuild";

const server = setupMockServer();

function renderApp(path: string, me: ReturnType<typeof makeUser> | null = null) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ME_KEY, me);
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>,
  );
  return router;
}

describe("app routes", () => {
  beforeEach(() => {
    server.use(
      http.get(`${API}/public/enquiries/options/`, () => ok({ boards: [], standards: [] })),
    );
  });

  it("loads a page's code on demand and names the browser tab after it", async () => {
    renderApp("/enquire");
    expect(await screen.findByRole("heading", { name: "Ask about admission" })).toBeInTheDocument();
    expect(document.title).toBe("Ask about admission · Chalkboard");
  });

  it("shows a friendly page for unknown links", async () => {
    renderApp("/no-such-page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(document.title).toBe("Page not found · Chalkboard");
  });

  it("gives staff a skip link to the page content", async () => {
    server.use(
      http.get(`${API}/staff/dashboard/`, () => ok(null)),
      http.get(`${API}/academics/boards/`, () => ok([])),
      http.get(`${API}/admin/enquiries/`, () => ok([])),
    );
    renderApp("/staff/account", makeUser());
    const skip = await screen.findByRole("link", { name: "Skip to content" });
    expect(skip).toHaveAttribute("href", "#main");
    expect(document.getElementById("main")?.tagName).toBe("MAIN");
  });
});

describe("RouteError", () => {
  const reload = vi.fn();
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal("location", { ...window.location, reload });
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    reload.mockReset();
  });

  const crashWith = (error: Error) => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          errorElement: <RouteError />,
          loader: () => {
            throw error;
          },
          element: <p>never shown</p>,
        },
      ],
      { initialEntries: ["/"] },
    );
    return render(<RouterProvider router={router} />);
  };

  it("after an update, reloads once to fetch the new version, then explains", async () => {
    const stale = new TypeError(
      "Failed to fetch dynamically imported module: /assets/FeesPage-old.js",
    );
    const first = crashWith(stale);
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    first.unmount();

    // Still failing after that reload: don't loop, say what to do.
    crashWith(stale);
    expect(await screen.findByText(/Chalkboard was updated/)).toBeInTheDocument();
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("shows other crashes with a reload button instead of a blank screen", async () => {
    crashWith(new Error("boom"));
    expect(
      await screen.findByRole("heading", { name: "Something went wrong" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();
  });

  it("recognises the browsers' stale-module errors", () => {
    expect(isStaleBuildError(new TypeError("Importing a module script failed."))).toBe(true);
    expect(isStaleBuildError(new Error("error loading dynamically imported module"))).toBe(true);
    expect(isStaleBuildError(new Error("Network Error"))).toBe(false);
  });
});
