/**
 * Tests & notes for staff (backend: /api/v1/staff/..., FAQ §8). The two share
 * almost everything (upload, versions, archive, assign), so every hook takes
 * the kind and builds the right URL.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  DocumentFile,
  Note,
  NoteAssignment,
  StaffStudent,
  TestAssignment,
  TestPaper,
} from "@/lib/api/types";
import { listQueryOptions } from "@/lib/useListParams";

export type Kind = "tests" | "notes";
export type LearningItem = TestPaper | Note;
export type FileKind = "PAPER" | "ANSWER_KEY" | "NOTE";

const key = (kind: Kind) => ["staff", kind] as const;
const itemUrl = (kind: Kind, id: number) => `staff/${kind}/${id}/`;

export function useItems(kind: Kind, params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...key(kind), "list", params],
    queryFn: () => api.list<LearningItem>(`staff/${kind}/`, params),
    ...listQueryOptions,
  });
}

export function useItem(kind: Kind, id: number) {
  return useQuery({
    queryKey: [...key(kind), id],
    queryFn: () => api.get<LearningItem>(itemUrl(kind, id)),
  });
}

export function useVersions(kind: Kind, id: number, enabled: boolean) {
  return useQuery({
    queryKey: [...key(kind), id, "versions"],
    queryFn: () => api.get<DocumentFile[]>(`${itemUrl(kind, id)}versions/`),
    enabled,
  });
}

/** Open a PDF in a new tab (files are only served to logged-in staff, never by public URL). */
export async function openPdf(kind: Kind, id: number, fileKind?: FileKind, version?: number) {
  // Open the tab first (inside the click), so pop-up blockers allow it.
  const tab = window.open("", "_blank");
  try {
    const params: Record<string, string | number> = {};
    if (fileKind && kind === "tests") params.kind = fileKind;
    if (version) params.version = version;
    const { blob } = await api.download(`${itemUrl(kind, id)}download/`, params);
    const url = URL.createObjectURL(blob);
    if (tab) tab.location.href = url;
    else window.location.href = url;
  } catch (error) {
    tab?.close();
    throw error;
  }
}

/** Refresh the item, its lists and its assignments after any change. */
function useLearningMutation<TVars, TResult>(kind: Kind, fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: key(kind) });
      void queryClient.invalidateQueries({ queryKey: ["staff", "assignments", kind] });
    },
  });
}

/** Multipart body: arrays become repeated fields, empty values are left out. */
export function toFormData(values: Record<string, unknown>): FormData {
  const form = new FormData();
  for (const [name, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => form.append(name, String(v)));
    else if (value instanceof Blob) form.append(name, value);
    else form.append(name, String(value));
  }
  return form;
}

export const useCreateItem = (kind: Kind) =>
  useLearningMutation(kind, (body: Record<string, unknown>) =>
    api.post<LearningItem>(`staff/${kind}/`, toFormData(body)),
  );

export const useUpdateItem = (kind: Kind, id: number) =>
  useLearningMutation(kind, (body: Record<string, unknown>) =>
    api.patch<LearningItem>(itemUrl(kind, id), body),
  );

export const useArchiveItem = (kind: Kind, id: number) =>
  useLearningMutation(kind, (archived: boolean) =>
    api.post<LearningItem>(`${itemUrl(kind, id)}archive/`, { archived }),
  );

/** Upload a new version of the main PDF (paper / notes) or the answer key. */
export const useReplaceFile = (kind: Kind, id: number) =>
  useLearningMutation(
    kind,
    ({
      file,
      answerKey,
      confirmDuplicate,
    }: {
      file: File;
      answerKey?: boolean;
      confirmDuplicate?: boolean;
    }) =>
      api.post<LearningItem>(
        `${itemUrl(kind, id)}${kind === "notes" ? "file" : answerKey ? "answer-key" : "paper"}/`,
        toFormData({ file, confirm_duplicate: confirmDuplicate ? "true" : undefined }),
      ),
  );

export const useRemoveAnswerKey = (id: number) =>
  useLearningMutation("tests", () => api.delete(`${itemUrl("tests", id)}answer-key/`));

// ── Assignments ────────────────────────────────────────────────────────
export type AssignResult = {
  assigned: unknown[];
  failed: { student_id: number; reason: string }[];
};

export function useAssignments(kind: Kind, itemId: number) {
  const filter = kind === "tests" ? "test_paper" : "note";
  return useQuery({
    queryKey: ["staff", "assignments", kind, itemId],
    queryFn: () =>
      api.list<TestAssignment | NoteAssignment>(
        `staff/${kind === "tests" ? "test" : "note"}-assignments/`,
        {
          [filter]: itemId,
          page_size: 100,
        },
      ),
  });
}

export const useAssign = (kind: Kind, id: number) =>
  useLearningMutation(
    kind,
    (body: {
      student_ids: number[];
      test_starts_at?: string | null;
      duration_minutes?: number | null;
      remarks?: string;
    }) => api.post<AssignResult>(`${itemUrl(kind, id)}assign/`, body),
  );

export const useRevokeAssignments = (kind: Kind) =>
  useLearningMutation(kind, (assignment_ids: number[]) =>
    api.post(`staff/${kind === "tests" ? "test" : "note"}-assignments/revoke/`, { assignment_ids }),
  );

export function useGrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, marks, remarks }: { id: number; marks: string | null; remarks: string }) =>
      api.post<TestAssignment>(`staff/test-assignments/${id}/grade/`, {
        marks_obtained: marks,
        grade_remarks: remarks,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["staff", "assignments", "tests"] }),
  });
}

/** Active students to assign to (minimal details; admins and teachers). */
export function useStaffStudents(filters: Record<string, string>) {
  return useQuery({
    queryKey: ["staff", "students", filters],
    queryFn: () => api.get<StaffStudent[]>("staff/students/", filters),
  });
}

export const FAILURE_REASON: Record<string, string> = {
  ALREADY_ASSIGNED: "already assigned",
  STUDENT_NOT_ACTIVE: "not an active student",
  NOT_FOUND: "not found",
};

export const SEMESTER_OPTIONS = [
  { value: "1", label: "Semester 1" },
  { value: "2", label: "Semester 2" },
];

export const isTest = (item: LearningItem): item is TestPaper => "max_marks" in item;
