import { Logo } from "@/components/shared/Logo";
import { session } from "@/lib/api/session";

/** Replaced by the real login screen in F1. Shows why a session ended. */
export function LoginPlaceholder() {
  const reason = session.getEndedReason();
  return (
    <main className="flex min-h-dvh items-center justify-center bg-board p-6">
      <div className="flex max-w-sm flex-col items-center gap-4 text-center">
        <Logo />
        <p className="text-board-text">The login screen arrives in step F1.</p>
        {reason && reason !== "LOGGED_OUT" && (
          <p className="text-sm text-board-muted">Your session ended ({reason}).</p>
        )}
      </div>
    </main>
  );
}
