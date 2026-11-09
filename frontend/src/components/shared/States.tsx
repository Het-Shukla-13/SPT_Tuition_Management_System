import { AlertTriangleIcon, InboxIcon, WifiOffIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/envelope";

/** "Nothing here yet" with an optional next step. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <InboxIcon className="size-8 text-muted" aria-hidden="true" />
      <p className="text-base font-bold">{title}</p>
      {description && <p className="max-w-md text-sm text-muted">{description}</p>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

/**
 * What went wrong, in plain words, with a retry and the request ID so the
 * exact server log line can be found.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null;
  const offline = apiError?.code === "NETWORK_ERROR";
  const Icon = offline ? WifiOffIcon : AlertTriangleIcon;
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-2 rounded-[var(--radius-card)] border border-line bg-surface px-6 py-10 text-center"
    >
      <Icon className="size-8 text-danger" aria-hidden="true" />
      <p className="text-base font-bold">{offline ? "You're offline" : "Something went wrong"}</p>
      <p className="max-w-md text-sm text-muted">
        {apiError?.message ?? "Please try again in a moment."}
      </p>
      {apiError?.requestId && (
        <p className="text-xs text-muted">
          Reference: <code className="tabular">{apiError.requestId.slice(0, 12)}</code>
        </p>
      )}
      {onRetry && (
        <Button variant="secondary" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
