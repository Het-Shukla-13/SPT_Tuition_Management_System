import { CheckIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { EmptyState, ErrorState } from "@/components/shared/States";
import { Skeleton } from "@/components/ui/skeleton";
import type { PortalStudent } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { usePortalStudents, useSelectStudent } from "../api";
import { ActiveStudentContext, pickStudent, studentName } from "../student";
import { StudentAvatar } from "./StudentAvatar";

/**
 * Decides which student the portal shows. A parent with several children picks
 * one ("Who's studying?"); the choice is remembered on this device.
 */
export function StudentGate({ children }: { children: ReactNode }) {
  const students = usePortalStudents();
  const select = useSelectStudent();
  const [choosing, setChoosing] = useState(false);

  if (students.isPending) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (students.error) {
    return (
      <div className="p-4">
        <ErrorState error={students.error} onRetry={() => void students.refetch()} />
      </div>
    );
  }
  if (students.data.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          title="No student is linked to this login yet"
          description="Please ask Sai Personal Tuitions to link your child to this account."
        />
      </div>
    );
  }

  const active = pickStudent(students.data);
  if (!active || choosing) {
    return (
      <StudentPicker
        students={students.data}
        current={active?.id}
        pending={select.isPending ? select.variables : undefined}
        onPick={(id) =>
          select.mutate(id, {
            onSuccess: () => setChoosing(false),
            onError: (e) => toast.error(e.message),
          })
        }
        onCancel={active ? () => setChoosing(false) : undefined}
      />
    );
  }

  return (
    <ActiveStudentContext.Provider
      value={{ student: active, students: students.data, choose: () => setChoosing(true) }}
    >
      {children}
    </ActiveStudentContext.Provider>
  );
}

function StudentPicker({
  students,
  current,
  pending,
  onPick,
  onCancel,
}: {
  students: PortalStudent[];
  current?: number;
  pending?: number;
  onPick: (id: number) => void;
  onCancel?: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-extrabold">Who's studying?</h1>
        <p className="text-sm text-muted">You can switch any time from the top of the screen.</p>
      </div>
      <ul className="flex flex-col gap-3">
        {students.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              disabled={pending !== undefined}
              onClick={() => onPick(s.id)}
              className={cn(
                "flex min-h-20 w-full items-center gap-4 rounded-[var(--radius-card)] border bg-surface p-4 text-left",
                s.id === current
                  ? "border-2 border-primary"
                  : "border-line hover:border-line-strong",
              )}
            >
              <StudentAvatar student={s} className="size-14 text-lg" />
              <span className="flex flex-1 flex-col">
                <b className="text-lg">{studentName(s)}</b>
                <span className="text-sm text-muted">
                  {s.standard.name} · {s.board.code}
                </span>
              </span>
              {pending === s.id ? (
                <span className="text-sm text-muted">Opening…</span>
              ) : (
                s.id === current && (
                  <CheckIcon className="size-5 text-primary" aria-label="Current" />
                )
              )}
            </button>
          </li>
        ))}
      </ul>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="min-h-11 self-center text-sm font-bold text-primary"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
