import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/envelope";

import { acceptInvite, checkInvite } from "../api";
import { AuthHeading, AuthLayout, FormAlert } from "../components/AuthLayout";

const schema = z
  .object({
    new_password: z.string().min(8, "Use at least 8 characters."),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "The two passwords don't match.",
  });
type Values = z.infer<typeof schema>;

/**
 * Opened from the invite email's single-use link. The person chooses their own
 * password, then signs in with it (pre-filled, with an "Invitation accepted" note).
 */
export function SetPasswordPage() {
  const [params] = useSearchParams();
  // Read once; the token is a secret, so it isn't kept around in the UI state.
  const [token] = useState(() => params.get("token") ?? "");
  const navigate = useNavigate();
  const invite = useQuery({
    queryKey: ["auth", "invite", token],
    queryFn: () => checkInvite(token),
    enabled: !!token,
    retry: false,
    staleTime: Infinity,
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm: "" },
  });
  const [error, setError] = useState<string | null>(null);

  const onSubmit = form.handleSubmit(async ({ new_password }) => {
    setError(null);
    try {
      const { email } = await acceptInvite({ token, new_password });
      navigate(`/login?invited=1&email=${encodeURIComponent(email)}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.new_password) {
        form.setError("new_password", { message: err.fieldErrors.new_password.join(" ") });
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      }
    }
  });

  if (token && invite.isPending) {
    return (
      <AuthLayout>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </AuthLayout>
    );
  }

  if (!token || invite.error || !invite.data) {
    const message =
      invite.error instanceof ApiError && invite.error.code !== "INVITE_LINK_INVALID"
        ? invite.error.message
        : "It may have expired or already been used. Ask the institute to send a new invite, or set your password with a code instead.";
    return (
      <AuthLayout>
        <AuthHeading title="This invite link didn't work" subtitle={message} />
        <Button asChild size="lg">
          <Link to="/reset-password">Set my password with a code</Link>
        </Button>
        <Link
          to="/login"
          className="flex min-h-11 items-center justify-center text-sm font-bold text-primary"
        >
          Back to log in
        </Link>
      </AuthLayout>
    );
  }

  const { first_name, email } = invite.data;
  return (
    <AuthLayout>
      <AuthHeading
        title={`Welcome${first_name ? `, ${first_name}` : ""}!`}
        subtitle={
          <>
            Choose a password for <b className="text-ink">{email}</b>. You'll use it to log in to
            Chalkboard.
          </>
        }
      />
      {error && <FormAlert>{error}</FormAlert>}
      <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-4" noValidate>
        {/* Lets password managers save the new password against the right email. */}
        <input type="email" name="username" autoComplete="username" value={email} readOnly hidden />
        <FormField
          label="New password"
          hint="At least 8 characters. Not a common password, and not just numbers."
          error={form.formState.errors.new_password?.message}
        >
          {(p) => (
            <PasswordInput {...p} {...form.register("new_password")} autoComplete="new-password" />
          )}
        </FormField>
        <FormField label="Type it again" error={form.formState.errors.confirm?.message}>
          {(p) => (
            <PasswordInput {...p} {...form.register("confirm")} autoComplete="new-password" />
          )}
        </FormField>
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Saving…" : "Set password"}
        </Button>
      </form>
      <p className="text-center text-xs leading-relaxed text-muted">
        Prefer Google? If {email} is your Google account, you can skip this and use “Continue with
        Google” on the login page.
      </p>
    </AuthLayout>
  );
}
