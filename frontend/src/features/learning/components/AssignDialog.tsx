import { useMemo, useState } from "react";
import { toast } from "sonner";

import { FilterBar, SearchInput } from "@/components/shared/FilterBar";
import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ReferenceFilter } from "@/features/academics";
import { ApiError } from "@/lib/api/envelope";

import {
  type AssignResult,
  FAILURE_REASON,
  isTest,
  type Kind,
  type LearningItem,
  useAssign,
  useStaffStudents,
} from "../api";

/**
 * Assign to students: starts with everyone in the item's class taking its
 * subject (all ticked), narrowed with filters/search. For tests, also when
 * the test starts (the answer key unlocks after start + duration).
 */
export function AssignDialog({
  kind,
  item,
  alreadyAssigned,
  onClose,
}: {
  kind: Kind;
  item: LearningItem;
  alreadyAssigned: number[];
  onClose: () => void;
}) {
  const [filters, setFilters] = useState({
    board: String(item.board),
    standard: String(item.standard),
    subject: String(item.subject),
    school: isTest(item) && item.school ? String(item.school) : "",
    search: "",
  });
  const students = useStaffStudents(
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
  );
  const available = useMemo(
    () => (students.data ?? []).filter((s) => !alreadyAssigned.includes(s.id)),
    [students.data, alreadyAssigned],
  );
  const [unticked, setUnticked] = useState<Set<number>>(new Set());
  const chosen = available.filter((s) => !unticked.has(s.id)).map((s) => s.id);
  const [startsAt, setStartsAt] = useState("");
  const [duration, setDuration] = useState(isTest(item) ? String(item.duration_minutes ?? "") : "");
  const assign = useAssign(kind, item.id);
  const [result, setResult] = useState<AssignResult | null>(null);
  const names = new Map((students.data ?? []).map((s) => [s.id, `${s.first_name} ${s.last_name}`]));

  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setUnticked(new Set());
  };
  const toggle = (id: number) =>
    setUnticked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const submit = () =>
    assign.mutate(
      {
        student_ids: chosen,
        ...(kind === "tests"
          ? {
              test_starts_at: startsAt ? new Date(startsAt).toISOString() : null,
              duration_minutes: duration ? Number(duration) : null,
            }
          : {}),
      },
      {
        onSuccess: (r) => {
          if (r.failed.length === 0) {
            toast.success(
              `Assigned to ${r.assigned.length} student${r.assigned.length === 1 ? "" : "s"}.`,
            );
            onClose();
          } else setResult(r);
        },
        onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't assign."),
      },
    );

  if (result) {
    return (
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent title="Assigned, with some skipped">
          <p>
            <b>Assigned to {result.assigned.length}.</b> {result.failed.length} skipped:
          </p>
          <ul className="list-disc pl-5 text-sm">
            {result.failed.map((f) => (
              <li key={f.student_id}>
                {names.get(f.student_id) ?? `Student #${f.student_id}`}:{" "}
                {FAILURE_REASON[f.reason] ?? f.reason.toLowerCase()}
              </li>
            ))}
          </ul>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !assign.isPending && onClose()}>
      <DialogContent title={`Assign "${item.title}"`} className="max-w-2xl">
        <FilterBar>
          <SearchInput
            value={filters.search}
            onChange={set("search")}
            placeholder="Name or admission no."
          />
          <ReferenceFilter
            resource="standards"
            label="Standard"
            allLabel="All standards"
            value={filters.standard}
            onChange={set("standard")}
          />
          <ReferenceFilter
            resource="subjects"
            label="Subject"
            allLabel="Any subject"
            value={filters.subject}
            onChange={set("subject")}
          />
          <ReferenceFilter
            resource="schools"
            label="School"
            allLabel="All schools"
            value={filters.school}
            onChange={set("school")}
          />
        </FilterBar>

        <div className="flex items-center justify-between text-sm">
          <span>
            <b>{chosen.length}</b> of {available.length} chosen
            {alreadyAssigned.length > 0 && (
              <span className="text-muted"> · already assigned students are hidden</span>
            )}
          </span>
          <span className="flex gap-1">
            <Button variant="ghost" size="sm" onClick={() => setUnticked(new Set())}>
              All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUnticked(new Set(available.map((s) => s.id)))}
            >
              None
            </Button>
          </span>
        </div>
        <ul
          className="flex max-h-72 flex-col overflow-y-auto rounded-[var(--radius-control)] border border-line"
          aria-label="Students"
        >
          {students.isPending && (
            <li className="px-3 py-3 text-sm text-muted">Loading students…</li>
          )}
          {!students.isPending && available.length === 0 && (
            <li className="px-3 py-3 text-sm text-muted">No students match. Change the filters.</li>
          )}
          {available.map((s) => (
            <li key={s.id} className="border-t border-line/70 first:border-t-0">
              <label className="flex min-h-11 cursor-pointer items-center gap-3 px-3 py-2 hover:bg-subtle">
                <input
                  type="checkbox"
                  checked={!unticked.has(s.id)}
                  onChange={() => toggle(s.id)}
                  className="size-5 accent-[var(--color-primary)]"
                />
                <span className="flex flex-col">
                  <b>
                    {s.first_name} {s.last_name}
                  </b>
                  <span className="text-xs text-muted">
                    {s.admission_number} · {s.standard_name} · {s.board_code} · {s.school_name}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>

        {kind === "tests" && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormField label="Test starts (optional)" hint="Needed for the answer key to unlock.">
              {(p) => (
                <Input
                  {...p}
                  type="datetime-local"
                  value={startsAt}
                  onChange={(e) => setStartsAt(e.target.value)}
                />
              )}
            </FormField>
            <FormField label="Duration (minutes)">
              {(p) => (
                <Input
                  {...p}
                  inputMode="numeric"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value.replace(/\D/g, ""))}
                />
              )}
            </FormField>
          </div>
        )}

        <div className="flex justify-end gap-2.5">
          <DialogClose asChild>
            <Button variant="secondary" disabled={assign.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={submit} disabled={assign.isPending || chosen.length === 0}>
            {assign.isPending ? "Assigning…" : `Assign to ${chosen.length}`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
