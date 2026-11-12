import { parseAsString, useQueryState } from "nuqs";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { FilterBar } from "@/components/shared/FilterBar";
import { Money } from "@/components/shared/Money";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/features/auth/session";
import { ReferenceFilter } from "@/features/academics";
import { methodLabel } from "@/features/fees";
import { formatDate, formatRelativeDay } from "@/lib/format";
import { cn } from "@/lib/utils";

import { type Dashboard, useDashboard, useNewEnquiryCount } from "../api";

/** The first screen for staff: today's numbers, what needs attention, recent activity. */
export function DashboardPage() {
  const me = useCurrentUser();
  const isAdmin = me.role === "ADMIN";
  const [board, setBoard] = useQueryState("board", parseAsString.withDefault(""));
  const dashboard = useDashboard({ board });
  const newEnquiries = useNewEnquiryCount(isAdmin);

  return (
    <>
      <PageHeader title={`Hello, ${me.first_name || "there"}`} eyebrow={formatDate(new Date())} />
      <FilterBar>
        <ReferenceFilter
          resource="boards"
          label="Board"
          allLabel="All boards"
          value={board}
          onChange={(v) => void setBoard(v || null)}
        />
      </FilterBar>
      {dashboard.isPending ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : dashboard.error ? (
        <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
      ) : (
        <Body data={dashboard.data} isAdmin={isAdmin} newEnquiries={newEnquiries.data ?? 0} />
      )}
    </>
  );
}

function Body({
  data,
  isAdmin,
  newEnquiries,
}: {
  data: Dashboard;
  isAdmin: boolean;
  newEnquiries: number;
}) {
  const { students, learning, fees } = data;
  return (
    <>
      {(learning.tests_to_grade > 0 || newEnquiries > 0 || (fees && fees.overdue > 0)) && (
        <Card className="gap-2 border-warning/40 bg-warning-bg" aria-label="Needs attention">
          <h2 className="font-extrabold text-warning">Needs attention</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {learning.tests_to_grade > 0 && (
              <Attention to="/staff/tests">
                {plural(learning.tests_to_grade, "test is", "tests are")} over and waiting for marks
              </Attention>
            )}
            {isAdmin && newEnquiries > 0 && (
              <Attention to="/staff/enquiries?status=NEW">
                {plural(newEnquiries, "new admission enquiry", "new admission enquiries")} to follow
                up
              </Attention>
            )}
            {fees && fees.overdue > 0 && (
              <Attention to="/staff/fees">
                {plural(fees.overdue, "student has", "students have")} overdue fees
              </Attention>
            )}
          </ul>
        </Card>
      )}

      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Active students"
          value={students.active}
          to="/staff/students"
          admin={isAdmin}
        />
        <Stat
          label={`New admissions (${students.new_admissions_days} days)`}
          value={students.new_admissions}
          to="/staff/students"
          admin={isAdmin}
        />
        <Stat
          label="Tests in the next 7 days"
          value={learning.upcoming_tests_7_days}
          to="/staff/tests"
          admin
        />
        <Stat
          label="Tests waiting for marks"
          value={learning.tests_to_grade}
          to="/staff/tests"
          admin
        />
        {fees && (
          <>
            <Stat
              label="Fees outstanding"
              value={<Money value={fees.total_outstanding} />}
              to="/staff/fees"
              admin
            />
            <Stat
              label="Fees collected"
              value={<Money value={fees.total_collected} />}
              to="/staff/fees?tab=payments"
              admin
            />
            <Stat
              label="Students with dues"
              value={`${fees.students_with_pending_fees} of ${fees.accounts}`}
              to="/staff/fees"
              admin
            />
            <Stat
              label="Year ending soon, still due"
              value={fees.ending_soon_with_dues}
              to="/staff/fees"
              admin
            />
          </>
        )}
      </section>
      {fees && <p className="-mt-2 text-xs text-muted">Fee figures cover the {fees.scope}.</p>}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Active students by standard" />
          <StandardBars rows={students.active_by_standard} />
        </Card>
        {fees ? (
          <Card>
            <CardHeader
              title="Recent payments"
              action={
                <Link to="/staff/fees?tab=payments" className="text-sm font-bold text-primary">
                  All payments
                </Link>
              }
            />
            <ActivityList
              empty="No payments yet."
              rows={fees.recent_payments.map((p) => ({
                key: p.id,
                title: p.student,
                detail: [formatDate(p.entry_date), methodLabel(p.method), p.receipt_number]
                  .filter(Boolean)
                  .join(" · "),
                end: (
                  <span className="flex items-center gap-2">
                    {p.reversed && <Badge tone="neutral">Reversed</Badge>}
                    <b className={cn(p.reversed && "text-muted line-through")}>
                      <Money value={p.amount} />
                    </b>
                  </span>
                ),
              }))}
            />
          </Card>
        ) : (
          <LearningCard title="Recent tests" to="/staff/tests" items={learning.recent_tests} />
        )}
        {isAdmin && (
          <Card>
            <CardHeader
              title="Recent admissions"
              action={
                <Link to="/staff/students/new" className="text-sm font-bold text-primary">
                  + New admission
                </Link>
              }
            />
            <ActivityList
              empty="No admissions yet."
              rows={students.recent_admissions.map((s) => ({
                key: s.id,
                to: `/staff/students/${s.id}`,
                title: s.name,
                detail: `${s.standard} · ${s.board} · ${s.admission_number}`,
                end: <span className="text-sm text-muted">{formatDate(s.admission_date)}</span>,
              }))}
            />
          </Card>
        )}
        {isAdmin && (
          <LearningCard title="Recent tests" to="/staff/tests" items={learning.recent_tests} />
        )}
        <LearningCard title="Recent notes" to="/staff/notes" items={learning.recent_notes} />
      </div>
    </>
  );
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function Attention({ to, children }: { to: string; children: ReactNode }) {
  return (
    <li>
      <Link to={to} className="font-semibold text-ink underline-offset-2 hover:underline">
        {children} →
      </Link>
    </li>
  );
}

function Stat({
  label,
  value,
  to,
  admin,
}: {
  label: string;
  value: ReactNode;
  to: string;
  admin: boolean;
}) {
  const body = (
    <>
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      <span className="tabular text-[28px] leading-tight font-extrabold">{value}</span>
    </>
  );
  const className =
    "flex flex-col gap-1 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3";
  // Teachers can't open the students list, so their student tiles aren't links.
  return admin ? (
    <Link to={to} className={cn(className, "hover:border-line-strong")}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** One series, so no legend: each bar is named and its count written beside it. */
function StandardBars({ rows }: { rows: Dashboard["students"]["active_by_standard"] }) {
  if (rows.length === 0) return <p className="text-sm text-muted">No active students.</p>;
  const max = Math.max(...rows.map((r) => r.count));
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Active students by standard</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Standard</th>
          <th scope="col">Active students</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.standard__level} title={`${r.standard__name}: ${r.count} active`}>
            <th scope="row" className="w-32 py-1.5 pr-3 text-left font-semibold whitespace-nowrap">
              {r.standard__name}
            </th>
            <td className="py-1.5">
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="h-3 rounded-r-[4px] bg-primary"
                  style={{ width: `${Math.max((r.count / max) * 85, 2)}%` }}
                />
                <span className="tabular font-bold">{r.count}</span>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type ActivityRow = { key: number; to?: string; title: string; detail: string; end?: ReactNode };

function ActivityList({ rows, empty }: { rows: ActivityRow[]; empty: string }) {
  if (rows.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="flex flex-col">
      {rows.map((r) => {
        const inner = (
          <>
            <span className="flex min-w-0 flex-1 flex-col">
              <b className="truncate">{r.title}</b>
              <span className="truncate text-xs text-muted">{r.detail}</span>
            </span>
            {r.end}
          </>
        );
        return (
          <li key={r.key} className="border-t border-line/70 first:border-t-0">
            {r.to ? (
              <Link to={r.to} className="flex min-h-12 items-center gap-3 py-2 hover:text-primary">
                {inner}
              </Link>
            ) : (
              <div className="flex min-h-12 items-center gap-3 py-2">{inner}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function LearningCard({
  title,
  to,
  items,
}: {
  title: string;
  to: string;
  items: Dashboard["learning"]["recent_tests"];
}) {
  return (
    <Card>
      <CardHeader
        title={title}
        action={
          <Link to={to} className="text-sm font-bold text-primary">
            See all
          </Link>
        }
      />
      <ActivityList
        empty="Nothing yet."
        rows={items.map((i) => ({
          key: i.id,
          to: `${to}/${i.id}`,
          title: i.title,
          detail: `${i.subject} · ${i.standard} · ${formatRelativeDay(i.created_at)}`,
        }))}
      />
    </Card>
  );
}
