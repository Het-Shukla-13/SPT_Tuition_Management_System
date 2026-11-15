import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { OtpInput } from "@/components/shared/OtpInput";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ApiError } from "@/lib/api/envelope";
import type { User } from "@/lib/api/types";

import { confirmPasswordReset, requestPasswordCode, useCompleteLogin } from "../api";

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
 * For people who have only ever used Google or codes: set a password, confirmed
 * with a code sent to their email (a logged-in session alone isn't enough).
 */
export function SetFirstPasswordCard({ user }: { user: User }) {
  const completeLogin = useCompleteLogin();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm: "" },
  });

  if (!user.email) {
    return (
      <Card>
        <CardHeader title="Password" />
        <p className="text-sm text-muted">
          You log in with a code sent to your phone, so you don't need a password. To use one, add
          an email under “My details” first.
        </p>
      </Card>
    );
  }
  const email = user.email;

  const send = async () => {
    setError(null);
    setSending(true);
    try {
      await requestPasswordCode({ email });
      setSentTo(email);
      setCode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send the code.");
    } finally {
      setSending(false);
    }
  };

  const onSubmit = form.handleSubmit(async ({ new_password }) => {
    if (code.length !== 6) return setError("Enter the 6-digit code from your email.");
    setError(null);
    try {
      // Saving a password ends other sessions; this one continues with the new login.
      completeLogin(await confirmPasswordReset({ email, code, new_password }));
      toast.success("Password set. You can now log in with your email and password too.");
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.new_password) {
        form.setError("new_password", { message: err.fieldErrors.new_password.join(" ") });
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      }
    }
  });

  return (
    <Card>
      <CardHeader title="Set a password" />
      {sentTo === null ? (
        <>
          <p className="text-sm text-muted">
            You don't have a password yet{user.google_linked ? " (you log in with Google)" : ""}.
            Set one to also log in with your email. We'll send a code to{" "}
            <b className="text-ink">{email}</b> to make sure it's you.
          </p>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <Button className="self-start" onClick={() => void send()} disabled={sending}>
            {sending ? "Sending…" : "Send code"}
          </Button>
        </>
      ) : (
        <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-4" noValidate>
          <p className="text-sm">
            We sent a 6-digit code to <b>{sentTo}</b>.
          </p>
          <OtpInput value={code} onChange={setCode} invalid={!!error} autoFocus />
          <FormField
            label="New password"
            hint="At least 8 characters. Not a common password, and not just numbers."
            error={form.formState.errors.new_password?.message}
          >
            {(p) => (
              <PasswordInput
                {...p}
                {...form.register("new_password")}
                autoComplete="new-password"
              />
            )}
          </FormField>
          <FormField label="Type it again" error={form.formState.errors.confirm?.message}>
            {(p) => (
              <PasswordInput {...p} {...form.register("confirm")} autoComplete="new-password" />
            )}
          </FormField>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Saving…" : "Set password"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void send()}
              disabled={sending}
            >
              Send a new code
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
