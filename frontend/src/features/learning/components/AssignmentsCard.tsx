import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError } from "@/lib/api/envelope";
import type { NoteAssignment, TestAssignment } from "@/lib/api/types";
import { formatDateTime, formatMarks } from "@/lib/format";

import {
  isTest,
  type Kind,
  type LearningItem,
  useAssignments,
  useGrade,
  useRevokeAssignments,
} from "../api";

type Row = TestAssignment | NoteAssignment;
const studentLabel = (r: Row) => `${r.student.first_name} ${r.student.last_name}`;

/** Who has this item. For tests: the marks grid (each row saves when you leave it). */
export function AssignmentsCard({
  kind,
  item,
  onAssign,
}: {
  kind: Kind;
  item: LearningItem;
  onAssign: () => void;
}) {
  const assignments = useAssignments(kind, item.id);
  const revoke = useRevokeAssignments(kind);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState(false);
  const rows = assignments.data?.items ?? [];
  const tests = kind === "tests";
  const maxMarks = isTest(item) ? item.max_marks : null;
  const graded = tests ? (rows as TestAssignment[]).filter((r) => r.marks_obtained !== null) : [];
  const average =
    graded.length > 0
      ? graded.reduce((sum, r) => sum + Number(r.marks_obtained), 0) / graded.length
      : null;

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <Card>
      <CardHeader
        title={tests ? "Students & marks" : "Students"}
        action={
          !item.is_archived && (
            <Button size="sm" onClick={onAssign}>
              + Assign students
            </Button>
          )
        }
      />
      {tests && rows.length > 0 && (
        <p className="-mt-2 text-sm text-muted">
          {graded.length} of {rows.length} marked
          {average !== null &&
            ` · average ${formatMarks(average.toFixed(2))} / ${formatMarks(maxMarks)}`}
        </p>
      )}
      {assignments.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : assignments.error ? (
        <ErrorState error={assignments.error} onRetry={() => void assignments.refetch()} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">Not assigned to anyone yet.</p>
      ) : (
        <>
          <Table>
            <caption className="sr-only">Assigned students</caption>
            <thead>
              <tr>
                <Th className="w-10">
                  <span className="sr-only">Select</span>
                </Th>
                <Th>Student</Th>
                {tests ? (
                  <>
                    <Th>Marks / {formatMarks(maxMarks)}</Th>
                    <Th>Remarks</Th>
                    <Th />
                  </>
                ) : (
                  <Th>Assigned</Th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <Tr key={row.id}>
                  <Td>
                    <input
                      type="checkbox"
                      aria-label={`Select ${studentLabel(row)}`}
                      checked={selected.has(row.id)}
                      onChange={() => toggle(row.id)}
                      className="size-5 accent-[var(--color-primary)]"
                    />
                  </Td>
                  <Td>
                    <span className="flex flex-col">
                      <b>{studentLabel(row)}</b>
                      <span className="tabular text-xs text-muted">
                        {row.student.admission_number}
                      </span>
                    </span>
                  </Td>
                  {tests ? (
                    <MarksCells row={row as TestAssignment} />
                  ) : (
                    <Td className="text-muted">{formatDateTime(row.assigned_at)}</Td>
                  )}
                </Tr>
              ))}
            </tbody>
          </Table>
          <div className="flex flex-wrap items-center justify-between gap-3">
            {tests ? (
              <span className="text-[13px] text-muted">
                Marks save as you leave each box. Clear the box to remove marks.
              </span>
            ) : (
              <span />
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={selected.size === 0}
              onClick={() => setConfirm(true)}
            >
              Remove {selected.size || ""} selected
            </Button>
          </div>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Remove ${selected.size} assignment${selected.size === 1 ? "" : "s"}?`}
        description="Those students won't see it any more. Entered marks are kept in the history."
        confirmLabel="Remove"
        pending={revoke.isPending}
        onConfirm={() =>
          revoke.mutate([...selected], {
            onSuccess: () => {
              setConfirm(false);
              setSelected(new Set());
              toast.success("Removed.");
            },
            onError: (e) => toast.error(e.message),
          })
        }
      />
    </Card>
  );
}

function MarksCells({ row }: { row: TestAssignment }) {
  const grade = useGrade();
  const max = Number(row.max_marks);
  const [marks, setMarks] = useState(
    row.marks_obtained === null ? "" : formatMarks(row.marks_obtained),
  );
  const [remarks, setRemarks] = useState(row.grade_remarks ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(row.marks_obtained !== null);
  const name = studentLabel(row);

  const save = () => {
    const trimmed = marks.trim();
    const original = row.marks_obtained === null ? "" : formatMarks(row.marks_obtained);
    if (trimmed === original && remarks === (row.grade_remarks ?? "")) return;
    if (trimmed && (!/^\d+(\.\d{1,2})?$/.test(trimmed) || Number(trimmed) > max)) {
      setError(`Must be between 0 and ${formatMarks(row.max_marks)}`);
      return;
    }
    setError(null);
    grade.mutate(
      { id: row.id, marks: trimmed || null, remarks: remarks.trim() },
      {
        onSuccess: () => setSaved(Boolean(trimmed)),
        onError: (e) => setError(e instanceof ApiError ? e.message : "Not saved"),
      },
    );
  };

  return (
    <>
      <Td>
        <Input
          aria-label={`Marks for ${name}`}
          aria-invalid={error ? true : undefined}
          className="h-10 w-24 text-right font-bold"
          inputMode="decimal"
          value={marks}
          onChange={(e) => {
            setMarks(e.target.value);
            setSaved(false);
          }}
          onBlur={save}
        />
      </Td>
      <Td>
        <Input
          aria-label={`Remarks for ${name}`}
          className="h-10 w-56"
          value={remarks}
          onChange={(e) => {
            setRemarks(e.target.value);
            setSaved(false);
          }}
          onBlur={save}
        />
      </Td>
      <Td>
        {error ? (
          <span className="text-[13px] text-danger">{error}</span>
        ) : grade.isPending ? (
          <span className="text-[13px] text-muted">Saving…</span>
        ) : saved ? (
          <Badge tone="success">Saved</Badge>
        ) : null}
      </Td>
    </>
  );
}
