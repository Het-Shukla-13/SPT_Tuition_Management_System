/** Admin user management (backend: /api/v1/admin/users/, FAQ §3). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { AdminUser, InviteResult, Role } from "@/lib/api/types";
import { listQueryOptions } from "@/lib/useListParams";

const USERS = ["admin", "users"] as const;

export function useUsers(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...USERS, "list", params],
    queryFn: () => api.list<AdminUser>("admin/users/", params),
    ...listQueryOptions,
  });
}

export function useUser(id: number) {
  return useQuery({
    queryKey: [...USERS, "detail", id],
    queryFn: () => api.get<AdminUser>(`admin/users/${id}/`),
  });
}

/** After any change: refresh this user and every users list. */
function useUserMutation<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: USERS }),
  });
}

export type InviteBody = {
  role: Role;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
};

export const useInviteUser = () =>
  useUserMutation((body: InviteBody) => api.post<InviteResult>("admin/users/", body));

export const useUpdateName = (id: number) =>
  useUserMutation((body: { first_name: string; last_name: string }) =>
    api.patch<AdminUser>(`admin/users/${id}/`, body),
  );

export const useSetActive = (id: number) =>
  useUserMutation((active: boolean) =>
    api.post<AdminUser>(`admin/users/${id}/${active ? "activate" : "deactivate"}/`),
  );

export const useResendInvite = (id: number) =>
  useUserMutation(() => api.post(`admin/users/${id}/resend-invite/`));

export const useChangeRole = (id: number) =>
  useUserMutation((role: Role) => api.post<AdminUser>(`admin/users/${id}/role/`, { role }));

export const useSetContact = (id: number) =>
  useUserMutation((body: { channel: "EMAIL" | "PHONE"; identifier: string | null }) =>
    api.post<AdminUser>(`admin/users/${id}/contact/`, body),
  );

export const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "ADMIN", label: "Admin" },
  { value: "TEACHER", label: "Teacher" },
  { value: "PORTAL", label: "Parent / student" },
];

/** "Invited" until their first login, then active/deactivated. */
export function userStatus(user: AdminUser): "ACTIVE" | "INACTIVE" | "INVITED" {
  if (!user.is_active) return "INACTIVE";
  return user.invite_accepted ? "ACTIVE" : "INVITED";
}
