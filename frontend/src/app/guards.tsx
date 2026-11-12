import { Link, Navigate, Outlet, useLocation } from "react-router";

import { LogoMark } from "@/components/shared/Logo";
import { ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { CurrentUserContext, homePathFor, useMe } from "@/features/auth/session";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import type { Role } from "@/lib/api/types";

export function FullPageLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center" aria-busy="true">
      <LogoMark className="size-12 animate-pulse" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/**
 * Protects a group of routes:
 * - not logged in → login page, remembering where you wanted to go;
 * - logged in with the wrong role → a "not allowed" page (never a blank screen);
 * - otherwise renders the routes, with the user available via useCurrentUser().
 */
export function RequireAuth({ roles }: { roles: Role[] }) {
  const { data: me, isPending, error, refetch } = useMe();
  const location = useLocation();

  if (isPending) return <FullPageLoader />;
  if (error) {
    return (
      <div className="mx-auto max-w-lg p-6 pt-24">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  }
  if (!me) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (!roles.includes(me.role)) return <NotAllowed home={homePathFor(me.role)} />;

  return (
    <CurrentUserContext.Provider value={me}>
      <Outlet />
    </CurrentUserContext.Provider>
  );
}

/** `/` → the right home for whoever is logged in. */
export function HomeRedirect() {
  const { data: me, isPending } = useMe();
  if (isPending) return <FullPageLoader />;
  return <Navigate to={me ? homePathFor(me.role) : "/login"} replace />;
}

export function NotAllowed({ home }: { home: string }) {
  useDocumentTitle("Not allowed");
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-3 p-6 text-center">
      <LogoMark className="size-12" />
      <h1 className="text-2xl font-extrabold">This page isn't for your account</h1>
      <p className="text-muted">
        Your login doesn't have access here. If you think it should, ask the institute office.
      </p>
      <Button asChild className="mt-2">
        <Link to={home}>Go to my home</Link>
      </Button>
    </main>
  );
}

export function NotFound() {
  useDocumentTitle("Page not found");
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-3 p-6 text-center">
      <LogoMark className="size-12" />
      <h1 className="text-2xl font-extrabold">Page not found</h1>
      <p className="text-muted">The link may be old or mistyped.</p>
      <Button asChild className="mt-2">
        <Link to="/">Go home</Link>
      </Button>
    </main>
  );
}
