import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError } from "@/lib/api/envelope";
import type { NoteAssignment, TestAssignment } from "@/lib/api/types";
import { formatDate, formatDateTime, formatMarks } from "@/lib/format";

import {
  isTest,
  type Kind,
  type LearningItem,
  useAssignments,
  useGrade,
  useRevokeAssignments,
  useUpdateTestAssignment,
} from "../api";
import { type Timing, timingBody, timingFrom } from "../timing";
import { TestTimingFields } from "./TestTimingFields";

type Row = TestAssignment | NoteAssignment;
const studentLabel = (r: Row) => `${r.student.first_name} ${r.student.last_name}`;

/** "Open now" · "15 Nov 2026, from 8:00 am" · "15 Nov 2026, 10:00 am · 60 min". */
function scheduleLabel(r: TestAssignment) {
  if (!r.test_starts_at) return "Open now";
  if (!r.has_start_time) return `${formatDate(r.test_starts_at)}, from 8:00 am`;
  return `${formatDateTime(r.test_starts_at)}${r.duration_minutes ? ` · ${r.duration_minutes} min` : ""}`;
}

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
  const [editingTime, setEditingTime] = useState(false);
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
                    <Th>Test time</Th>
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
                    <>
                      <Td className="text-sm whitespace-nowrap text-muted">
                        {scheduleLabel(row as TestAssignment)}
                      </Td>
                      <MarksCells row={row as TestAssignment} />
                    </>
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
                Marks open once a student's test is over, and save as you leave each box.
              </span>
            ) : (
              <span />
            )}
            <span className="flex gap-2">
              {tests && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={selected.size === 0}
                  onClick={() => setEditingTime(true)}
                >
                  Edit time{selected.size ? ` (${selected.size})` : ""}
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                disabled={selected.size === 0}
                onClick={() => setConfirm(true)}
              >
                Remove {selected.size || ""} selected
              </Button>
            </span>
          </div>
        </>
      )}
      {editingTime && (
        <EditTimeDialog
          rows={(rows as TestAssignment[]).filter((r) => selected.has(r.id))}
          onClose={() => setEditingTime(false)}
        />
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
          disabled={!row.is_over && marks === ""}
          placeholder={row.is_over ? "" : "After test"}
          title={row.is_over ? undefined : "Marks open once the test is over"}
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

/** Reschedule the selected students' test: one date, optional time and duration for all. */
function EditTimeDialog({ rows, onClose }: { rows: TestAssignment[]; onClose: () => void }) {
  const update = useUpdateTestAssignment();
  const first = rows[0];
  const [timing, setTiming] = useState<Timing>(() =>
    timingFrom(
      first?.test_starts_at,
      Boolean(first?.has_start_time),
      String(first?.duration_minutes ?? ""),
    ),
  );
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setError(null);
    try {
      for (const row of rows) await update.mutateAsync({ id: row.id, body: timingBody(timing) });
      toast.success(`Updated the time for ${rows.length} student${rows.length === 1 ? "" : "s"}.`);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update the time.");
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !update.isPending && onClose()}>
      <DialogContent
        title={`Edit test time (${rows.length} student${rows.length === 1 ? "" : "s"})`}
      >
        <TestTimingFields value={timing} onChange={setTiming} />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2.5">
          <DialogClose asChild>
            <Button variant="secondary" disabled={update.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={() => void save()} disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
