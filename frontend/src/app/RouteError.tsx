import { isRouteErrorResponse, Link, useRouteError } from "react-router";

import { LogoMark } from "@/components/shared/Logo";
import { Button } from "@/components/ui/button";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

import { NotFound } from "./guards";
import { isStaleBuildError, reloadOnceForUpdate } from "./staleBuild";

/** Shown when a page crashes or can't load, instead of a blank screen. */
export function RouteError({ inShell = false }: { inShell?: boolean }) {
  const error = useRouteError();
  useDocumentTitle("Something went wrong");

  if (isRouteErrorResponse(error) && error.status === 404 && !inShell) return <NotFound />;
  if (isStaleBuildError(error) && reloadOnceForUpdate()) return null;

  if (import.meta.env.DEV) console.error(error);
  // The shells already provide the <main> landmark.
  const Wrapper = inShell ? "div" : "main";
  return (
    <Wrapper
      role={inShell ? "alert" : undefined}
      className={
        inShell
          ? "mx-auto flex max-w-md flex-col items-center gap-3 p-6 py-16 text-center"
          : "mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-3 p-6 text-center"
      }
    >
      {!inShell && <LogoMark className="size-12" />}
      <h1 className="text-2xl font-extrabold">Something went wrong</h1>
      <p className="text-muted">
        {isStaleBuildError(error)
          ? "Chalkboard was updated. Reload to get the new version."
          : "This page couldn't be shown. Reloading usually fixes it; if not, please tell the institute office."}
      </p>
      <div className="mt-2 flex gap-2.5">
        <Button onClick={() => window.location.reload()}>Reload</Button>
        <Button asChild variant="secondary">
          <Link to="/" reloadDocument>
            Go home
          </Link>
        </Button>
      </div>
    </Wrapper>
  );
}
