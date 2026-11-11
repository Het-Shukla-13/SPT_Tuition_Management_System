import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import { session } from "@/lib/api/session";
import { useCountdown } from "@/lib/useCountdown";

import {
  type Authenticated,
  type AuthResult,
  type CodeRequired,
  googleSignIn,
  googleVerify,
  loginWithPassword,
  resendNewDeviceCode,
  useCompleteLogin,
  verifyNewDevice,
} from "../api";
import { AuthHeading, AuthLayout, FormAlert } from "../components/AuthLayout";
import { CodeStep } from "../components/CodeStep";
import { GoogleButton } from "../components/GoogleButton";
import { safeNext } from "../redirect";
import { homePathFor, useMe } from "../session";

const schema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

/** Pending code step: from a password login (ticket) or from Google (id token). */
type PendingCode =
  | { kind: "password"; ticket: string; info: CodeRequired }
  | { kind: "google"; idToken: string; info: CodeRequired };

const ENDED_MESSAGES: Record<string, string> = {
  LOGGED_OUT: "You've been logged out.",
  SESSION_EXPIRED: "Your session ended. Please log in again.",
  NO_ACTIVE_ACCOUNT: "Your session ended. Please log in again.",
  TOKEN_NOT_VALID: "Your session ended. Please log in again.",
};

export function LoginPage() {
  const { data: me } = useMe();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const completeLogin = useCompleteLogin();
  const [pending, setPending] = useState<PendingCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wait = useCountdown();
  const [notice] = useState(() => {
    const reason = session.getEndedReason();
    return reason ? (ENDED_MESSAGES[reason] ?? null) : null;
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });
  const email = useWatch({ control: form.control, name: "email" });

  if (me) return <Navigate to={safeNext(params.get("next")) ?? homePathFor(me.role)} replace />;

  const finish = (result: Authenticated) => {
    completeLogin(result);
    navigate(safeNext(params.get("next")) ?? homePathFor(result.user.role), { replace: true });
  };

  const handleError = (err: unknown) => {
    if (err instanceof ApiError) {
      if (err.retryAfterSeconds) wait.start(err.retryAfterSeconds);
      for (const [field, messages] of Object.entries(err.fieldErrors)) {
        if (field === "email" || field === "password")
          form.setError(field, { message: messages[0] });
      }
      setError(err.message);
    } else {
      setError("Something went wrong. Please try again.");
    }
  };

  const handleResult = (result: AuthResult, onCode: (info: CodeRequired) => PendingCode) => {
    if (result.status === "AUTHENTICATED") finish(result);
    else setPending(onCode(result));
  };

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await loginWithPassword(values);
      handleResult(result, (info) => ({ kind: "password", ticket: info.login_ticket ?? "", info }));
    } catch (err) {
      handleError(err);
    }
  });

  const onGoogle = async (idToken: string) => {
    setError(null);
    try {
      handleResult(await googleSignIn({ id_token: idToken }), (info) => ({
        kind: "google",
        idToken,
        info,
      }));
    } catch (err) {
      handleError(err);
    }
  };

  if (pending) {
    const back = () => {
      setPending(null);
      form.setValue("password", "");
    };
    return (
      <AuthLayout>
        <CodeStep
          email={pending.info.email}
          resendAfterSeconds={pending.info.resend_after_seconds}
          reason={
            pending.kind === "google"
              ? "To keep your account safe, we check new devices and new Google links with a code."
              : undefined
          }
          onBack={back}
          onVerify={async (code) => {
            try {
              finish(
                pending.kind === "password"
                  ? await verifyNewDevice({ login_ticket: pending.ticket, code })
                  : await googleVerify({ id_token: pending.idToken, code }),
              );
            } catch (err) {
              if (err instanceof ApiError && err.code === "LOGIN_TICKET_INVALID") {
                back();
                setError(err.message);
                return;
              }
              throw err;
            }
          }}
          onResend={
            pending.kind === "password"
              ? async () =>
                  (await resendNewDeviceCode({ login_ticket: pending.ticket })).resend_after_seconds
              : undefined
          }
        />
      </AuthLayout>
    );
  }

  const locked = wait.remaining > 0;

  return (
    <AuthLayout>
      <AuthHeading title="Log in" subtitle="Use the email the institute has for you." />
      {notice && !error && <FormAlert tone="info">{notice}</FormAlert>}
      {error && (
        <FormAlert>
          {error}
          {locked && (
            <>
              {" "}
              Try again in <b className="tabular">{wait.label}</b>.
            </>
          )}
        </FormAlert>
      )}

      <GoogleButton onCredential={(token) => void onGoogle(token)} />
      <div className="flex items-center gap-3 text-[13px] text-muted" aria-hidden="true">
        <span className="h-px flex-1 bg-line" />
        or
        <span className="h-px flex-1 bg-line" />
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormField label="Email" error={form.formState.errors.email?.message}>
          {(p) => (
            <Input
              {...p}
              {...form.register("email")}
              type="email"
              autoComplete="username"
              inputMode="email"
            />
          )}
        </FormField>
        <FormField label="Password" error={form.formState.errors.password?.message}>
          {(p) => (
            <PasswordInput {...p} {...form.register("password")} autoComplete="current-password" />
          )}
        </FormField>
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting || locked}>
          {form.formState.isSubmitting
            ? "Logging in…"
            : locked
              ? `Try again in ${wait.label}`
              : "Log in"}
        </Button>
      </form>

      <Link
        to={`/reset-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
        className="flex min-h-11 items-center justify-center text-sm font-bold text-primary"
      >
        First time here, or forgot your password?
      </Link>
      <p className="text-center text-xs leading-relaxed text-muted">
        Logins are created by the institute. New devices are checked with a code sent to your email.
      </p>
    </AuthLayout>
  );
}
