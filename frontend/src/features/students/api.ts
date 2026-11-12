/** Students (backend: /api/v1/admin/students/, FAQ §6). Admin only. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  AcademicHistory,
  AdminUser,
  AdmissionResult,
  FeeAccountListItem,
  StudentDetail,
  StudentListItem,
  StudentStatus,
} from "@/lib/api/types";
import { listQueryOptions } from "@/lib/useListParams";

const STUDENTS = ["admin", "students"] as const;
const base = (id: number) => `admin/students/${id}/`;

export function useStudents(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...STUDENTS, "list", params],
    queryFn: () => api.list<StudentListItem>("admin/students/", params),
    ...listQueryOptions,
  });
}

export function useStudent(id: number) {
  return useQuery({ queryKey: [...STUDENTS, id], queryFn: () => api.get<StudentDetail>(base(id)) });
}

export function useStudentHistory(id: number) {
  return useQuery({
    queryKey: [...STUDENTS, id, "history"],
    queryFn: () => api.get<AcademicHistory[]>(`${base(id)}history/`),
  });
}

export function useStudentFeeAccounts(id: number) {
  return useQuery({
    queryKey: ["admin", "fees", "student", id],
    queryFn: () => api.get<FeeAccountListItem[]>(`admin/fees/students/${id}/accounts/`),
  });
}

/** The student's photo as a local object URL (photos are never public URLs). */
export function useStudentPhoto(id: number, hasPhoto: boolean) {
  return useQuery({
    queryKey: [...STUDENTS, id, "photo"],
    queryFn: async () => URL.createObjectURL((await api.download(`${base(id)}photo/`)).blob),
    enabled: hasPhoto,
    staleTime: Infinity,
  });
}

/** Parent/student logins, for "link an existing login" pickers. */
export function usePortalLogins(search: string) {
  return useQuery({
    queryKey: ["admin", "users", "portal-search", search],
    queryFn: async () =>
      (
        await api.list<AdminUser>("admin/users/", {
          role: "PORTAL",
          is_active: "true",
          search,
          page_size: 10,
        })
      ).items,
    enabled: search.trim().length >= 2,
  });
}

/** Mutations on one student refresh it, its history, the lists and its fees. */
function useStudentMutation<TVars, TResult>(
  id: number | null,
  fn: (vars: TVars) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: id === null ? STUDENTS : [...STUDENTS, id] });
      void queryClient.invalidateQueries({ queryKey: [...STUDENTS, "list"] });
      if (id !== null)
        void queryClient.invalidateQueries({ queryKey: ["admin", "fees", "student", id] });
    },
  });
}

export type NewLogin = { first_name: string; last_name: string; email: string; phone?: string };

export type AdmissionBody = {
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  gender?: string;
  address?: string;
  guardian_name?: string;
  guardian_relation?: string;
  guardian_phone?: string;
  guardian_email?: string;
  remarks?: string;
  board: number;
  standard: number;
  school: number;
  admission_date?: string;
  subjects: number[];
  link_user_ids: number[];
  new_logins: NewLogin[];
  agreed_fee?: string | null;
  opening_balance?: string;
  opening_balance_reason?: string;
  confirm_duplicate?: boolean;
};

export const useAdmitStudent = () =>
  useStudentMutation(null, (body: AdmissionBody) =>
    api.post<AdmissionResult>("admin/students/", body),
  );

export const useUpdateStudent = (id: number) =>
  useStudentMutation(id, (body: Partial<AdmissionBody>) =>
    api.patch<StudentDetail>(base(id), body),
  );

export const useChangeAcademic = (id: number) =>
  useStudentMutation(
    id,
    (body: { board?: number; standard?: number; school?: number; reason: string }) =>
      api.post<StudentDetail>(`${base(id)}academic/`, body),
  );

export const useSetStudentStatus = (id: number) =>
  useStudentMutation(id, (status: StudentStatus) =>
    api.post<StudentDetail>(`${base(id)}status/`, { status }),
  );

export const useSetSubjects = (id: number) =>
  useStudentMutation(id, (subjects: number[]) =>
    api.post<StudentDetail>(`${base(id)}subjects/`, { subjects }),
  );

export const useGrantAccess = (id: number) =>
  useStudentMutation(id, (body: { user_id: number } | { new_login: NewLogin }) =>
    api.post<StudentDetail>(`${base(id)}access/`, body),
  );

export const useRevokeAccess = (id: number) =>
  useStudentMutation(id, (userId: number) =>
    api.delete<StudentDetail>(`${base(id)}access/${userId}/`),
  );

export function useStudentPhotoMutations(id: number) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: [...STUDENTS, id] });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("photo", file);
      return api.post<StudentDetail>(`${base(id)}photo/`, form);
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`${base(id)}photo/`),
    onSuccess: refresh,
  });
  return { upload, remove };
}

export const STATUS_OPTIONS: { value: StudentStatus; label: string }[] = [
  { value: "ACTIVE", label: "Active" },
  { value: "ON_HOLD", label: "On hold" },
  { value: "LEFT", label: "Left the institute" },
  { value: "COMPLETED", label: "Course completed" },
];

export const GENDER_OPTIONS = [
  { value: "MALE", label: "Male" },
  { value: "FEMALE", label: "Female" },
  { value: "OTHER", label: "Other" },
];

export const CHANGE_REASONS = [
  { value: "PROMOTION", label: "Promotion to the next standard" },
  { value: "REPEAT", label: "Repeating the same standard" },
  { value: "SCHOOL_CHANGE", label: "Changed school" },
  { value: "BOARD_CHANGE", label: "Changed board" },
  { value: "CORRECTION", label: "Correction of a mistake" },
];

export const studentName = (s: { first_name: string; last_name: string }) =>
  `${s.first_name} ${s.last_name}`.trim();
