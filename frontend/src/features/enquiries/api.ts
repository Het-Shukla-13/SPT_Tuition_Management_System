/**
 * Admission enquiries (backend: /api/v1/public/enquiries/ and /api/v1/admin/enquiries/).
 * The public form only stores a request; it never creates a login or a student.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { Enquiry } from "@/lib/api/types";

const ENQUIRIES = ["admin", "enquiries"] as const;

export function useEnquiries(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...ENQUIRIES, "list", params],
    queryFn: () => api.list<Enquiry>("admin/enquiries/", params),
  });
}

export function useEnquiry(id: number | null) {
  return useQuery({
    queryKey: [...ENQUIRIES, "detail", id],
    queryFn: () => api.get<Enquiry>(`admin/enquiries/${id}/`),
    enabled: id !== null,
  });
}

export type EnquiryUpdate = { status?: string; notes?: string; student?: number | null };

export function useUpdateEnquiry(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EnquiryUpdate) => api.patch<Enquiry>(`admin/enquiries/${id}/`, body),
    onSuccess: (enquiry) => {
      queryClient.setQueryData([...ENQUIRIES, "detail", id], enquiry);
      void queryClient.invalidateQueries({ queryKey: ENQUIRIES });
    },
  });
}

// ── Public form (no login) ─────────────────────────────────────────────
export type EnquiryOptions = {
  boards: { id: number; code: string; name: string }[];
  standards: { id: number; name: string }[];
};

export function useEnquiryOptions() {
  return useQuery({
    queryKey: ["public", "enquiry-options"],
    queryFn: () => api.get<EnquiryOptions>("public/enquiries/options/"),
    staleTime: 60 * 60_000,
  });
}

export type PublicEnquiryBody = {
  parent_name: string;
  phone: string;
  email?: string;
  student_name: string;
  standard?: number | null;
  board?: number | null;
  message?: string;
  website?: string;
};

export function useSubmitEnquiry() {
  return useMutation({
    mutationFn: (body: PublicEnquiryBody) => api.post<null>("public/enquiries/", body),
  });
}

export const ENQUIRY_STATUSES = [
  { value: "NEW", label: "New" },
  { value: "CONTACTED", label: "Contacted" },
  { value: "ACCEPTED", label: "Admitted" },
  { value: "REJECTED", label: "Not proceeding" },
];

/** "Aarav Kumar Shah" → first "Aarav", last "Kumar Shah", for pre-filling the admission form. */
export function splitName(full: string): { first: string; last: string } {
  const [first = "", ...rest] = full.trim().split(/\s+/);
  return { first, last: rest.join(" ") };
}
