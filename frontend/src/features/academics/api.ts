/**
 * Academic reference data (backend: /api/v1/academics/, FAQ §5): boards,
 * standards, subjects, chapters, schools, academic years.
 * Anyone logged in reads ACTIVE items; admins also see inactive ones and
 * create/edit. Nothing is deleted: items are deactivated (history stays valid).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { listQueryOptions } from "@/lib/useListParams";

export type ReferenceKey =
  "academic-years" | "boards" | "standards" | "subjects" | "schools" | "chapters";

export type ReferenceItem = { id: number; is_active: boolean } & Record<string, unknown>;

const KEY = ["academics"] as const;

export function useReferenceList(resource: ReferenceKey, params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...KEY, resource, "list", params],
    queryFn: () => api.list<ReferenceItem>(`academics/${resource}/`, params),
    ...listQueryOptions,
  });
}

/**
 * Every ACTIVE item of a type, for dropdowns anywhere in the app
 * (admission form, test upload, filters). Cached for 5 minutes.
 */
export function useReferenceOptions<T extends ReferenceItem = ReferenceItem>(
  resource: ReferenceKey,
  filters: Record<string, string | number> = {},
  enabled = true,
) {
  return useQuery({
    queryKey: [...KEY, resource, "options", filters],
    queryFn: async () =>
      (
        await api.list<T>(`academics/${resource}/`, {
          ...filters,
          is_active: "true",
          page_size: 100,
        })
      ).items,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useSaveReference(resource: ReferenceKey) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<ReferenceItem>(`academics/${resource}/${id}/`, body)
        : api.post<ReferenceItem>(`academics/${resource}/`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...KEY, resource] }),
  });
}
