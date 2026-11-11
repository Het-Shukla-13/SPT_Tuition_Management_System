import { ArrowLeftIcon } from "lucide-react";
import { type FormEvent, useState } from "react";

import { OtpInput } from "@/components/shared/OtpInput";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/envelope";
import { useCountdown } from "@/lib/useCountdown";

import { AuthHeading, FormAlert } from "./AuthLayout";

/**
 * "Enter the code we emailed you": used by the new-device step of a password
 * login and by Google's first-link / new-device step.
 */
export function CodeStep({
  email,
  resendAfterSeconds,
  onVerify,
  onResend,
  onBack,
  reason = "This device is new, so we emailed you a code to make sure it's you.",
}: {
  email: string | null;
  resendAfterSeconds: number;
  onVerify: (code: string) => Promise<void>;
  /** Omitted when resending isn't possible here (Google: sign in with Google again). */
  onResend?: () => Promise<number>;
  onBack: () => void;
  reason?: string;
}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const resend = useCountdown(resendAfterSeconds);

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (code.length !== 6 || pending) return;
    setPending(true);
    setError(null);
    try {
      await onVerify(code);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setCode("");
    } finally {
      setPending(false);
    }
  };

  const doResend = async () => {
    if (!onResend) return;
    setError(null);
    try {
      resend.start(await onResend());
      setCode("");
    } catch (err) {
      if (err instanceof ApiError && err.retryAfterSeconds) resend.start(err.retryAfterSeconds);
      setError(err instanceof ApiError ? err.message : "Couldn't send a new code.");
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <button
        type="button"
        onClick={onBack}
        className="flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" /> Back
      </button>
      <AuthHeading
        title="Enter your code"
        subtitle={
          <>
            {reason} It went to <b className="text-ink">{email ?? "your email"}</b> and works for 5
            minutes.
          </>
        }
      />
      {error && <FormAlert>{error}</FormAlert>}
      <OtpInput
        value={code}
        onChange={(next) => {
          setCode(next);
          if (error) setError(null);
        }}
        invalid={!!error}
        disabled={pending}
        autoFocus
      />
      <Button type="submit" size="lg" disabled={code.length !== 6 || pending}>
        {pending ? "Checking…" : "Verify & log in"}
      </Button>
      {onResend && (
        <p className="text-center text-sm text-muted">
          {resend.remaining > 0 ? (
            <>
              Resend code in <b className="tabular text-ink">{resend.label}</b>
            </>
          ) : (
            <button type="button" onClick={doResend} className="min-h-11 font-bold text-primary">
              Send a new code
            </button>
          )}
        </p>
      )}
    </form>
  );
}
