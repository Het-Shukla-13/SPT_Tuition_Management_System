/**
 * Every auth call the screens make (backend: docs/frontend/api-guide.md §4).
 * A successful login of any kind goes through `useCompleteLogin`, so the
 * token, the cached user and the redirect are handled in one place.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { session } from "@/lib/api/session";
import type { TrustedDevice, User, UserSession } from "@/lib/api/types";

import { ME_KEY } from "./session";

export type Authenticated = { status: "AUTHENTICATED"; access: string; user: User };
export type CodeRequired = {
  status: "OTP_REQUIRED";
  /** Masked address the code went to, e.g. k****a@example.com */
  email: string | null;
  /** Password logins only: send back with the code. */
  login_ticket?: string;
  expires_in_seconds: number;
  resend_after_seconds: number;
};
export type AuthResult = Authenticated | CodeRequired;

/** Store the new login: token in memory, user in the cache (guards see it at once). */
export function useCompleteLogin() {
  const queryClient = useQueryClient();
  return (result: Authenticated) => {
    session.setAccessToken(result.access);
    queryClient.setQueryData(ME_KEY, result.user);
  };
}

// ── Email + password ───────────────────────────────────────────────────
export const loginWithPassword = (body: { email: string; password: string }) =>
  api.post<AuthResult>("auth/login/", body);

export const verifyNewDevice = (body: { login_ticket: string; code: string }) =>
  api.post<Authenticated>("auth/login/verify/", body);

export const resendNewDeviceCode = (body: { login_ticket: string }) =>
  api.post<CodeRequired>("auth/login/resend/", body);

// ── Set or reset password ──────────────────────────────────────────────
export const requestPasswordCode = (body: { email: string }) =>
  api.post<CodeRequired>("auth/password/reset/", body);

export const confirmPasswordReset = (body: { email: string; code: string; new_password: string }) =>
  api.post<Authenticated>("auth/password/reset/confirm/", body);

// ── Google ─────────────────────────────────────────────────────────────
export const googleSignIn = (body: { id_token: string }) =>
  api.post<AuthResult>("auth/google/", body);

export const googleVerify = (body: { id_token: string; code: string }) =>
  api.post<Authenticated>("auth/google/verify/", body);

// ── Account (logged in) ────────────────────────────────────────────────
const SESSIONS_KEY = ["auth", "sessions"] as const;
const DEVICES_KEY = ["auth", "devices"] as const;

export function useSessions() {
  return useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: () => api.get<UserSession[]>("auth/sessions/"),
  });
}

export function useTrustedDevices() {
  return useQuery({
    queryKey: DEVICES_KEY,
    queryFn: () => api.get<TrustedDevice[]>("auth/devices/"),
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`auth/sessions/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSIONS_KEY }),
  });
}

export function useRemoveDevice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`auth/devices/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DEVICES_KEY }),
  });
}

export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.post("auth/password/change/", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
      void queryClient.invalidateQueries({ queryKey: DEVICES_KEY });
    },
  });
}

// ── My details (every role can edit their own) ──────────────────────────
/** Every change here returns the updated user, which becomes the cached "me". */
function useMeMutation<TVars>(fn: (vars: TVars) => Promise<User>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (user) => queryClient.setQueryData(ME_KEY, user),
  });
}

export type ContactChannel = "EMAIL" | "PHONE";

export const useUpdateMyName = () =>
  useMeMutation((body: { first_name: string; last_name: string }) =>
    api.patch<User>("auth/me/", body),
  );

/** Step 1: send a code to the NEW email/phone. Returns where it went and how long it lasts. */
export function useRequestContactChange() {
  return useMutation({
    mutationFn: (body: { channel: ContactChannel; identifier: string }) =>
      api.post<{ sent_to: string; expires_in_seconds: number }>("auth/me/contact/", body),
  });
}

/** Step 2: confirm the code; the new email/phone is saved as verified. */
export const useVerifyContactChange = () =>
  useMeMutation((body: { channel: ContactChannel; identifier: string; code: string }) =>
    api.post<User>("auth/me/contact/verify/", body),
  );

export const useRemoveContact = () =>
  useMeMutation((channel: ContactChannel) =>
    api.delete<User>(`auth/me/contact/${channel === "EMAIL" ? "email" : "phone"}/`),
  );

export const useUnlinkGoogle = () => useMeMutation(() => api.post<User>("auth/google/unlink/"));
