import { type ReactNode, useCallback, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { Money } from "@/components/shared/Money";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useReferenceOptions } from "@/features/academics";
import { SubjectFeeFollowUp } from "@/features/fees";
import type { StudentDetail } from "@/lib/api/types";
import { formatDate, formatPhone } from "@/lib/format";
import { mediumLabel } from "@/lib/options";

import {
  GENDER_OPTIONS,
  studentName,
  useSetSubjects,
  useStudent,
  useStudentFeeAccounts,
  useStudentHistory,
} from "../api";
import { LoginsCard } from "../components/LoginsCard";
import {
  ChangeClassDialog,
  ChangeStatusDialog,
  EditDetailsDialog,
} from "../components/StudentDialogs";
import { StudentPhoto } from "../components/StudentPhoto";

type Open = "details" | "class" | "status" | null;

export function StudentDetailPage() {
  const id = Number(useParams().id);
  const student = useStudent(id);
  const [open, setOpen] = useState<Open>(null);

  if (student.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-20 w-80" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }
  if (student.error)
    return <ErrorState error={student.error} onRetry={() => void student.refetch()} />;
  const s = student.data;

  return (
    <>
      <PageHeader
        back={{ to: "/staff/students", label: "Students" }}
        title={studentName(s)}
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <span className="tabular">{s.admission_number}</span> · {s.standard.name} ·{" "}
            {s.board.code} · {s.school.name}
            <StatusBadge status={s.status ?? "ACTIVE"} />
          </span>
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => setOpen("details")}>
              Edit details
            </Button>
            <Button variant="secondary" onClick={() => setOpen("class")}>
              Change class
            </Button>
            <Button variant="secondary" onClick={() => setOpen("status")}>
              Change status
            </Button>
          </>
        }
      />
      <StudentPhoto student={s} />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,400px),1fr))] gap-5">
        <DetailsCard student={s} />
        <FeesCard studentId={s.id} />
        <SubjectsCard student={s} />
        <LoginsCard student={s} />
        <HistoryCard studentId={s.id} />
      </div>

      {open === "details" && (
        <EditDetailsDialog student={s} open onOpenChange={() => setOpen(null)} />
      )}
      {open === "class" && (
        <ChangeClassDialog student={s} open onOpenChange={() => setOpen(null)} />
      )}
      {open === "status" && (
        <ChangeStatusDialog student={s} open onOpenChange={() => setOpen(null)} />
      )}
    </>
  );
}

function Rows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="font-semibold break-words">{value || "–"}</dd>
        </div>
      ))}
    </dl>
  );
}

function DetailsCard({ student: s }: { student: StudentDetail }) {
  const gender = GENDER_OPTIONS.find((g) => g.value === s.gender)?.label;
  const guardian = [
    s.guardian_name,
    s.guardian_relation && `(${s.guardian_relation.toLowerCase()})`,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Card>
      <CardHeader title="Details" />
      <Rows
        rows={[
          ["Date of birth", s.date_of_birth ? formatDate(s.date_of_birth) : ""],
          ["Gender", gender ?? ""],
          ["Medium", mediumLabel(s.medium)],
          ["Admitted", formatDate(s.admission_date)],
          ...(s.left_on ? ([["Left on", formatDate(s.left_on)]] as [string, ReactNode][]) : []),
          ["Guardian", guardian],
          ["Guardian phone", s.guardian_phone ? formatPhone(s.guardian_phone) : ""],
          ["Guardian email", s.guardian_email ?? ""],
          ["Address", s.address ?? ""],
          ["Remarks", s.remarks ?? ""],
        ]}
      />
    </Card>
  );
}

function FeesCard({ studentId }: { studentId: number }) {
  const accounts = useStudentFeeAccounts(studentId);
  return (
    <Card>
      <CardHeader title="Fees" />
      {accounts.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : accounts.error ? (
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
      ) : accounts.data.length === 0 ? (
        <p className="text-sm text-muted">No fee account yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {accounts.data.map((a) => (
            <li
              key={a.id}
              className="flex flex-col gap-2 border-t border-line/70 pt-3 first:border-t-0 first:pt-0"
            >
              <span className="flex items-center justify-between gap-2 text-sm">
                <Link
                  to={`/staff/fees/accounts/${a.id}`}
                  className="font-bold text-primary hover:underline"
                >
                  {a.board} {a.academic_year_name} · {a.standard}
                </Link>
                <StatusBadge status={a.status} />
              </span>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Total" value={<Money value={a.total} />} />
                <Stat label="Paid" value={<Money value={a.paid} tone="paid" />} />
                <Stat
                  label="Pending"
                  value={
                    <Money value={a.pending} tone={Number(a.pending) > 0 ? "due" : undefined} />
                  }
                />
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">
        Open a year to record payments, print receipts or adjust the fee.
      </p>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="flex flex-col">
      <span className="text-xs text-muted">{label}</span>
      <span className="text-lg font-extrabold">{value}</span>
    </span>
  );
}

function SubjectsCard({ student }: { student: StudentDetail }) {
  const current =
    (student.subjects as unknown as {
      subject: { id: number; name: string };
      started_on: string;
    }[]) ?? [];
  const options = useReferenceOptions("subjects");
  const setSubjects = useSetSubjects(student.id);
  const [editing, setEditing] = useState<number[] | null>(null);
  const [changed, setChanged] = useState<{
    added: { id: number; name: string }[];
    dropped: { id: number; name: string }[];
  } | null>(null);
  const closeFollowUp = useCallback(() => setChanged(null), []);

  const save = (next: number[]) => {
    const before = current.map((c) => c.subject.id);
    const named = (id: number) => ({
      id,
      name: String(
        options.data?.find((o) => o.id === id)?.name ??
          current.find((c) => c.subject.id === id)?.subject.name ??
          "",
      ),
    });
    setSubjects.mutate(next, {
      onSuccess: () => {
        setEditing(null);
        toast.success("Subjects updated.");
        // Optional subjects (e.g. Gujarati) may have their own fee: offer to update it.
        const added = next.filter((id) => !before.includes(id)).map(named);
        const dropped = before.filter((id) => !next.includes(id)).map(named);
        if (added.length || dropped.length) setChanged({ added, dropped });
      },
      onError: (e) => toast.error(e.message),
    });
  };

  return (
    <Card>
      <CardHeader
        title="Subjects"
        action={
          editing === null && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditing(current.map((c) => c.subject.id))}
            >
              Change
            </Button>
          )
        }
      />
      {editing === null ? (
        <div className="flex flex-wrap gap-2">
          {current.length === 0 && <span className="text-sm text-muted">No subjects.</span>}
          {current.map((c) => (
            <Badge key={c.subject.id} tone="brand" className="px-3 py-1 text-sm">
              {c.subject.name}
            </Badge>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <ChipToggleGroup
            label="Current subjects"
            options={(options.data ?? []).map((o) => ({ value: o.id, label: String(o.name) }))}
            value={editing}
            onChange={setEditing}
            loading={options.isPending}
          />
          <p className="text-xs text-muted">
            Dropped subjects keep their history; added ones start today.
          </p>
          <div className="flex gap-2.5">
            <Button
              size="sm"
              disabled={setSubjects.isPending || editing.length === 0}
              onClick={() => save(editing)}
            >
              Save subjects
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {changed && (
        <SubjectFeeFollowUp
          studentId={student.id}
          standardId={student.standard.id}
          added={changed.added}
          dropped={changed.dropped}
          onClose={closeFollowUp}
        />
      )}
    </Card>
  );
}

function HistoryCard({ studentId }: { studentId: number }) {
  const history = useStudentHistory(studentId);
  return (
    <Card>
      <CardHeader title="Academic history" />
      {history.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : history.error ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : (
        <ol className="flex flex-col">
          {history.data.map((h) => (
            <li
              key={h.id}
              className="flex flex-col border-t border-line/70 py-2.5 text-sm first:border-t-0"
            >
              <b>
                {h.academic_year} · {h.board} · {h.standard}
              </b>
              <span className="text-muted">
                {h.school} · {formatDate(h.started_on)}
                {h.ended_on ? ` – ${formatDate(h.ended_on)}` : " – now"} ·{" "}
                {String(h.reason).replaceAll("_", " ").toLowerCase()}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
