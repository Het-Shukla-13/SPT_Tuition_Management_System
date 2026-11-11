import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeftIcon } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { OtpInput } from "@/components/shared/OtpInput";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import { useCountdown } from "@/lib/useCountdown";

import { confirmPasswordReset, requestPasswordCode, useCompleteLogin } from "../api";
import { AuthHeading, AuthLayout, FormAlert } from "../components/AuthLayout";
import { homePathFor, useMe } from "../session";

const emailSchema = z.object({ email: z.email("Enter a valid email address.") });

const passwordSchema = z
  .object({
    code: z.string().regex(/^\d{6}$/, "Enter the 6-digit code."),
    new_password: z.string().min(8, "Use at least 8 characters."),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    message: "The passwords don't match.",
    path: ["confirm"],
  });

/**
 * "Set or reset password": an invited user's first visit, or a forgotten
 * password. Email → code → new password → logged in on this device.
 */
export function ResetPasswordPage() {
  const { data: me } = useMe();
  const [params] = useSearchParams();
  const [email, setEmail] = useState<string | null>(null);

  if (me) return <Navigate to={homePathFor(me.role)} replace />;
  return (
    <AuthLayout>
      {email ? (
        <NewPasswordStep email={email} onBack={() => setEmail(null)} />
      ) : (
        <EmailStep initialEmail={params.get("email") ?? ""} onSent={setEmail} />
      )}
    </AuthLayout>
  );
}

function EmailStep({
  initialEmail,
  onSent,
}: {
  initialEmail: string;
  onSent: (email: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: initialEmail },
  });

  const onSubmit = form.handleSubmit(async ({ email }) => {
    setError(null);
    try {
      await requestPasswordCode({ email });
      onSent(email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  });

  return (
    <>
      <Link
        to="/login"
        className="flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" /> Back to log in
      </Link>
      <AuthHeading
        title="Set or reset your password"
        subtitle="First time here, or forgot your password? We'll email you a code, then you choose a password."
      />
      {error && <FormAlert>{error}</FormAlert>}
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
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Sending…" : "Send code"}
        </Button>
      </form>
    </>
  );
}

function NewPasswordStep({ email, onBack }: { email: string; onBack: () => void }) {
  const navigate = useNavigate();
  const completeLogin = useCompleteLogin();
  const [error, setError] = useState<string | null>(null);
  const resend = useCountdown(60);
  const form = useForm({
    resolver: zodResolver(passwordSchema),
    defaultValues: { code: "", new_password: "", confirm: "" },
  });
  const code = useWatch({ control: form.control, name: "code" });

  const onSubmit = form.handleSubmit(async ({ code, new_password }) => {
    setError(null);
    try {
      const result = await confirmPasswordReset({ email, code, new_password });
      completeLogin(result);
      navigate(homePathFor(result.user.role), { replace: true });
    } catch (err) {
      if (!(err instanceof ApiError)) return setError("Something went wrong. Please try again.");
      const passwordErrors = err.fieldErrors.new_password;
      if (passwordErrors) form.setError("new_password", { message: passwordErrors.join(" ") });
      else setError(err.message);
      if (err.code.startsWith("OTP_")) form.setValue("code", "");
    }
  });

  const resendCode = async () => {
    setError(null);
    try {
      await requestPasswordCode({ email });
      resend.start(60);
    } catch (err) {
      if (err instanceof ApiError && err.retryAfterSeconds) resend.start(err.retryAfterSeconds);
      setError(err instanceof ApiError ? err.message : "Couldn't send a new code.");
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={onBack}
        className="flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" /> Change email
      </button>
      <AuthHeading
        title="Choose your password"
        subtitle={
          <>
            If <b className="text-ink">{email}</b> has an account, a 6-digit code is on its way.
          </>
        }
      />
      {error && <FormAlert>{error}</FormAlert>}
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold">Code from the email</span>
          <OtpInput
            value={code}
            onChange={(v) =>
              form.setValue("code", v, { shouldValidate: form.formState.isSubmitted })
            }
            invalid={!!form.formState.errors.code}
            autoFocus
          />
          {form.formState.errors.code && (
            <span className="text-[13px] text-danger">{form.formState.errors.code.message}</span>
          )}
        </div>
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
          {form.formState.isSubmitting ? "Saving…" : "Save password & log in"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted">
        {resend.remaining > 0 ? (
          <>
            Resend code in <b className="tabular text-ink">{resend.label}</b>
          </>
        ) : (
          <button type="button" onClick={resendCode} className="min-h-11 font-bold text-primary">
            Send a new code
          </button>
        )}
      </p>
    </>
  );
}
