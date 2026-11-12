import { ChevronRightIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { Money } from "@/components/shared/Money";
import { ErrorState } from "@/components/shared/States";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDateTime, formatMarks } from "@/lib/format";

import { type Overview, useOverview } from "../api";
import { PortalHeader } from "../components/PortalHeader";
import { StudentAvatar } from "../components/StudentAvatar";
import { studentName, useActiveStudent } from "../student";

export function PortalHomePage() {
  const { student } = useActiveStudent();
  const overview = useOverview(student.id);

  return (
    <div className="flex flex-col gap-4 p-4">
      <PortalHeader title="Home" />
      <Card className="flex-row items-center gap-4">
        <StudentAvatar student={student} className="size-16 text-xl" />
        <div className="flex min-w-0 flex-col">
          <b className="truncate text-xl">{studentName(student)}</b>
          <span className="text-sm text-muted">
            {student.standard.name} · {student.board.code} · {student.school.name}
          </span>
          {student.status && student.status !== "ACTIVE" && (
            <span className="pt-1">
              <StatusBadge status={student.status} />
            </span>
          )}
        </div>
      </Card>

      {overview.isPending ? (
        <>
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-40 w-full" />
        </>
      ) : overview.error ? (
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      ) : (
        <>
          {overview.data.fees && <FeesSummary fees={overview.data.fees} />}
          <Section
            title="Upcoming tests"
            more={{ to: "/portal/tests", label: "All tests" }}
            empty="No tests coming up."
          >
            {overview.data.upcoming_tests.map((t) => (
              <Row key={t.assignment_id} to={`/portal/tests/${t.assignment_id}`} title={t.title}>
                {t.subject} · {formatDateTime(t.test_starts_at)}
              </Row>
            ))}
          </Section>
          <Section
            title="Recent results"
            more={{ to: "/portal/tests?view=past", label: "All results" }}
            empty="No marks yet."
          >
            {overview.data.recent_results.map((r) => (
              <Row
                key={r.assignment_id}
                to={`/portal/tests/${r.assignment_id}`}
                title={r.title}
                end={
                  <b className="tabular text-base">
                    {formatMarks(r.marks_obtained)}
                    <span className="text-sm font-semibold text-muted">
                      /{formatMarks(r.max_marks)}
                    </span>
                  </b>
                }
              >
                {r.subject}
              </Row>
            ))}
          </Section>
          <Section
            title="New notes"
            more={{ to: "/portal/notes", label: "All notes" }}
            empty="No notes shared yet."
          >
            {overview.data.recent_notes.map((n) => (
              <Row
                key={n.assignment_id}
                to={`/portal/notes?search=${encodeURIComponent(n.title)}`}
                title={n.title}
              >
                {n.subject} · shared {formatDate(n.assigned_at)}
              </Row>
            ))}
          </Section>
        </>
      )}
    </div>
  );
}

function FeesSummary({ fees }: { fees: NonNullable<Overview["fees"]> }) {
  const pending = Number(fees.pending);
  const earlier = Number(fees.pending_all_years) - pending;
  return (
    <Link to="/portal/fees" className="block">
      <Card className="gap-2 hover:border-line-strong">
        <span className="flex items-center justify-between gap-2">
          <b>Fees {fees.academic_year}</b>
          <span className="flex gap-1.5">
            <StatusBadge status={fees.status} />
            {fees.is_overdue && <Badge tone="danger">Overdue</Badge>}
          </span>
        </span>
        {pending > 0 ? (
          <p>
            <span className="text-2xl font-extrabold">
              <Money value={fees.pending} tone="due" />
            </span>{" "}
            <span className="text-sm text-muted">pending · due by {formatDate(fees.due_date)}</span>
          </p>
        ) : Number(fees.credit) > 0 ? (
          <p className="text-sm">
            Fully paid, with <Money value={fees.credit} /> paid in advance.
          </p>
        ) : (
          <p className="text-sm font-semibold text-success">Fully paid for this year. Thank you!</p>
        )}
        {earlier > 0 && (
          <p className="text-sm text-warning">
            Plus <Money value={earlier} /> from earlier years.
          </p>
        )}
        <span className="text-sm font-bold text-primary">See payments and receipts</span>
      </Card>
    </Link>
  );
}

function Section({
  title,
  more,
  empty,
  children,
}: {
  title: string;
  more: { to: string; label: string };
  empty: string;
  children: ReactNode[];
}) {
  return (
    <Card className="gap-1 pb-2">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-extrabold">{title}</h2>
        <Link to={more.to} className="flex min-h-11 items-center text-sm font-bold text-primary">
          {more.label}
        </Link>
      </div>
      {children.length ? (
        <ul className="flex flex-col">{children}</ul>
      ) : (
        <p className="pb-3 text-sm text-muted">{empty}</p>
      )}
    </Card>
  );
}

function Row({
  to,
  title,
  end,
  children,
}: {
  to: string;
  title: string;
  end?: ReactNode;
  children: ReactNode;
}) {
  return (
    <li className="border-t border-line/70 first:border-t-0">
      <Link to={to} className="flex min-h-14 items-center gap-3 py-2">
        <span className="flex min-w-0 flex-1 flex-col">
          <b className="truncate">{title}</b>
          <span className="text-sm text-muted">{children}</span>
        </span>
        {end ?? <ChevronRightIcon className="size-5 text-muted" aria-hidden="true" />}
      </Link>
    </li>
  );
}
