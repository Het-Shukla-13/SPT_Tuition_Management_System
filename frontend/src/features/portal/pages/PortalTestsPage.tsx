import { ChevronRightIcon } from "lucide-react";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { Link } from "react-router";

import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import type { PortalTest } from "@/lib/api/types";
import { formatDateTime, formatMarks } from "@/lib/format";
import { cn } from "@/lib/utils";

import { isUpcoming, usePortalTests } from "../api";
import { PortalHeader } from "../components/PortalHeader";
import { useActiveStudent } from "../student";

const VIEWS = ["upcoming", "past"] as const;

export function PortalTestsPage() {
  const { student } = useActiveStudent();
  const tests = usePortalTests(student.id);
  const [view, setView] = useQueryState(
    "view",
    parseAsStringLiteral(VIEWS).withDefault("upcoming"),
  );

  const all = tests.data ?? [];
  const upcoming = all
    .filter((t) => isUpcoming(t))
    .sort((a, b) =>
      (a.test_starts_at ?? a.test_ends_at).localeCompare(b.test_starts_at ?? b.test_ends_at),
    );
  const past = all
    .filter((t) => !isUpcoming(t))
    .sort((a, b) => b.test_ends_at.localeCompare(a.test_ends_at));
  const shown = view === "upcoming" ? upcoming : past;

  return (
    <div className="flex flex-col gap-4 p-4">
      <PortalHeader title="Tests" />
      <div
        role="tablist"
        aria-label="Which tests"
        className="grid grid-cols-2 rounded-full bg-neutral-bg p-1"
      >
        {VIEWS.map((v) => (
          <button
            key={v}
            type="button"
            role="tab"
            aria-selected={view === v}
            onClick={() => void setView(v === "upcoming" ? null : v)}
            className={cn(
              "min-h-11 rounded-full text-sm font-bold",
              view === v ? "bg-surface text-primary shadow-sm" : "text-muted",
            )}
          >
            {v === "upcoming" ? `Upcoming (${upcoming.length})` : `Past (${past.length})`}
          </button>
        ))}
      </div>
      {tests.isPending ? (
        <>
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </>
      ) : tests.error ? (
        <ErrorState error={tests.error} onRetry={() => void tests.refetch()} />
      ) : shown.length === 0 ? (
        <EmptyState title={view === "upcoming" ? "No tests coming up" : "No past tests yet"} />
      ) : (
        <ul className="flex flex-col gap-3">
          {shown.map((t) => (
            <li key={t.id}>
              <TestCard test={t} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TestCard({ test }: { test: PortalTest }) {
  const graded = test.marks_obtained != null;
  return (
    <Link
      to={`/portal/tests/${test.id}`}
      className="flex items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-line-strong"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="text-xs font-bold tracking-wide text-muted uppercase">{test.subject}</span>
        <b className="text-base">{test.title}</b>
        <span className="text-sm text-muted">
          {formatDateTime(test.test_starts_at ?? test.test_ends_at)}
        </span>
        {!isUpcoming(test) && !graded && (
          <span>
            <Badge tone="neutral">Marks not added yet</Badge>
          </span>
        )}
      </span>
      {graded ? (
        <b className="tabular text-xl">
          {formatMarks(test.marks_obtained)}
          <span className="text-sm font-semibold text-muted">/{formatMarks(test.max_marks)}</span>
        </b>
      ) : (
        <ChevronRightIcon className="size-5 text-muted" aria-hidden="true" />
      )}
    </Link>
  );
}
