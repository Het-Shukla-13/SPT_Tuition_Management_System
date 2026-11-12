/**
 * Parent & student portal (backend: /api/v1/portal/students/...). Read-only:
 * every request names the student, and the server checks this login is linked to them.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { openFile } from "@/lib/api/openFile";
import type { PortalFeeAccount, PortalNote, PortalStudent, PortalTest } from "@/lib/api/types";

const PORTAL = ["portal"] as const;
const base = (studentId: number) => `portal/students/${studentId}/`;

export function usePortalStudents() {
  return useQuery({
    queryKey: [...PORTAL, "students"],
    queryFn: () => api.get<PortalStudent[]>("portal/students/"),
  });
}

/** Remember the chosen student on this device (the server checks access on every request anyway). */
export function useSelectStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<{ selected_student_id: number }>(`${base(id)}select/`),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<PortalStudent[]>([...PORTAL, "students"], (students) =>
        students?.map((s) => ({ ...s, is_selected: s.id === id })),
      );
    },
  });
}

export function useStudentPhotoUrl(id: number, hasPhoto: boolean) {
  return useQuery({
    queryKey: [...PORTAL, "photo", id],
    queryFn: async () => URL.createObjectURL((await api.download(`${base(id)}photo/`)).blob),
    enabled: hasPhoto,
    staleTime: Infinity,
  });
}

// The overview is a hand-built dict on the server, so it has no generated type.
export type Overview = {
  student: {
    id: number;
    admission_number: string;
    first_name: string;
    last_name: string;
    standard: string;
    board: string;
    school: string;
    status: string;
    has_photo: boolean;
  };
  upcoming_tests: {
    assignment_id: number;
    title: string;
    subject: string;
    test_starts_at: string | null;
  }[];
  recent_results: {
    assignment_id: number;
    title: string;
    subject: string;
    marks_obtained: string;
    max_marks: string;
  }[];
  recent_notes: { assignment_id: number; title: string; subject: string; assigned_at: string }[];
  fees: {
    academic_year: string;
    due_date: string;
    total: string;
    paid: string;
    pending: string;
    credit: string;
    status: string;
    is_overdue: boolean;
    pending_all_years: string;
  } | null;
};

export function useOverview(studentId: number) {
  return useQuery({
    queryKey: [...PORTAL, studentId, "overview"],
    queryFn: () => api.get<Overview>(`${base(studentId)}overview/`),
  });
}

export function usePortalTests(studentId: number) {
  return useQuery({
    queryKey: [...PORTAL, studentId, "tests"],
    queryFn: () => api.get<PortalTest[]>(`${base(studentId)}tests/`),
  });
}

export function usePortalTest(studentId: number, id: number) {
  return useQuery({
    queryKey: [...PORTAL, studentId, "tests", id],
    queryFn: () => api.get<PortalTest>(`${base(studentId)}tests/${id}/`),
  });
}

export function usePortalNotes(studentId: number) {
  return useQuery({
    queryKey: [...PORTAL, studentId, "notes"],
    queryFn: () => api.get<PortalNote[]>(`${base(studentId)}notes/`),
  });
}

export function usePortalFees(studentId: number) {
  return useQuery({
    queryKey: [...PORTAL, studentId, "fees"],
    queryFn: () => api.get<PortalFeeAccount[]>(`${base(studentId)}fees/`),
  });
}

export const openTestFile = (studentId: number, id: number, kind: "PAPER" | "ANSWER_KEY") =>
  openFile(`${base(studentId)}tests/${id}/download/`, { kind, inline: "true" });

export const openNote = (studentId: number, id: number) =>
  openFile(`${base(studentId)}notes/${id}/download/`, { inline: "true" });

export const openPortalReceipt = (studentId: number, entryId: number) =>
  openFile(`${base(studentId)}fees/receipts/${entryId}/`);

/** Upcoming until it ends; the answer key and marks only make sense after that. */
export const isUpcoming = (test: Pick<PortalTest, "test_ends_at">, now = Date.now()) =>
  new Date(test.test_ends_at).getTime() > now;

/** Notes are few per student, so search and the subject filter work on the loaded list, instantly. */
export function filterNotes(notes: PortalNote[], search: string, subject: string) {
  const term = search.trim().toLowerCase();
  return notes.filter(
    (n) =>
      (!subject || String(n.subject_id) === subject) &&
      (!term ||
        [n.title, n.subject, ...n.chapters].some((text) => text.toLowerCase().includes(term))),
  );
}
