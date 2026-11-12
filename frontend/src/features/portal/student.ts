import { createContext, useContext } from "react";

import type { PortalStudent } from "@/lib/api/types";

export type ActiveStudent = {
  student: PortalStudent;
  students: PortalStudent[];
  /** Open the "Who's studying?" picker (only offered when there is more than one). */
  choose: () => void;
};

export const ActiveStudentContext = createContext<ActiveStudent | null>(null);

/** The student the portal is showing. Only usable inside <StudentGate>. */
export function useActiveStudent(): ActiveStudent {
  const value = useContext(ActiveStudentContext);
  if (!value) throw new Error("useActiveStudent must be used inside <StudentGate>.");
  return value;
}

export const studentName = (s: Pick<PortalStudent, "first_name" | "last_name">) =>
  `${s.first_name} ${s.last_name}`.trim();

/** Which student to show without asking: the one this device picked, or the only one. */
export function pickStudent(students: PortalStudent[]): PortalStudent | null {
  return (
    students.find((s) => s.is_selected) ?? (students.length === 1 ? (students[0] ?? null) : null)
  );
}
