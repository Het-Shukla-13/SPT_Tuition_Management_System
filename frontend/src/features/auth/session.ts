/**
 * Who is logged in, as React Query state.
 *
 * On app start (or a page reload) there's no access token in memory, so we
 * try the refresh cookie once: if it works the user is silently logged back
 * in; if not, they're logged out (null). Network trouble is an error, not a
 * logout, so a bad connection doesn't throw people out.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext } from "react";

import { api, refreshAccessToken } from "@/lib/api/client";
import { ApiError } from "@/lib/api/envelope";
import { session } from "@/lib/api/session";
import type { Role, User } from "@/lib/api/types";

export const ME_KEY = ["auth", "me"] as const;

function isLoggedOutError(error: unknown) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export async function loadCurrentUser(): Promise<User | null> {
  try {
    if (!session.getAccessToken()) await refreshAccessToken();
    return await api.get<User>("auth/me/");
  } catch (error) {
    if (isLoggedOutError(error)) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: loadCurrentUser, staleTime: Infinity, retry: 1 });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("auth/logout/"),
    // Log out locally even if the server call fails (e.g. offline).
    onSettled: () => {
      session.clear("LOGGED_OUT");
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
    },
  });
}

/** Where each role lands after logging in. */
export function homePathFor(role: Role): string {
  return role === "PORTAL" ? "/portal" : "/staff";
}

/** The logged-in user, provided by the route guard to everything inside it. */
export const CurrentUserContext = createContext<User | null>(null);

export function useCurrentUser(): User {
  const user = useContext(CurrentUserContext);
  if (!user) throw new Error("useCurrentUser() used outside a logged-in route.");
  return user;
}

export function displayName(user: Pick<User, "first_name" | "last_name" | "email" | "phone">) {
  const name = `${user.first_name} ${user.last_name}`.trim();
  return name || user.email || user.phone || "Account";
}

export const ROLE_LABEL: Record<Role, string> = {
  ADMIN: "Admin",
  TEACHER: "Teacher",
  PORTAL: "Parent / student",
};
