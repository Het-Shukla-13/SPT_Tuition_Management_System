import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeftIcon, MailIcon, SmartphoneIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import { session } from "@/lib/api/session";
import { GOOGLE_CLIENT_ID } from "@/lib/config";
import { formatPhone } from "@/lib/format";
import { useCountdown } from "@/lib/useCountdown";

import {
  type Authenticated,
  type AuthResult,
  type CodeRequired,
  googleSignIn,
  googleVerify,
  loginWithPassword,
  requestPhoneCode,
  resendNewDeviceCode,
  useCompleteLogin,
  useSignInMethods,
  verifyNewDevice,
  verifyPhoneCode,
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

/** Pending code step: password login (ticket), Google (id token) or phone (SMS). */
type PendingCode =
  | { kind: "password"; ticket: string; email: string | null; resendAfter: number }
  | { kind: "google"; idToken: string; email: string | null; resendAfter: number }
  | { kind: "phone"; phone: string; resendAfter: number };

type Method = "choose" | "email" | "phone";

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
  const methods = useSignInMethods();
  const invited = params.get("invited") === "1";
  const [method, setMethod] = useState<Method>(invited ? "email" : "choose");
  const [pending, setPending] = useState<PendingCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wait = useCountdown();
  const [notice] = useState(() => {
    const reason = session.getEndedReason();
    return reason ? (ENDED_MESSAGES[reason] ?? null) : null;
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: params.get("email") ?? "", password: "" },
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

  const onCode = (result: AuthResult, toPending: (info: CodeRequired) => PendingCode) => {
    if (result.status === "AUTHENTICATED") finish(result);
    else setPending(toPending(result));
  };

  const onPassword = form.handleSubmit(async (values) => {
    setError(null);
    try {
      onCode(await loginWithPassword(values), (info) => ({
        kind: "password",
        ticket: info.login_ticket ?? "",
        email: info.email,
        resendAfter: info.resend_after_seconds,
      }));
    } catch (err) {
      handleError(err);
    }
  });

  const onGoogle = async (idToken: string) => {
    setError(null);
    try {
      onCode(await googleSignIn({ id_token: idToken }), (info) => ({
        kind: "google",
        idToken,
        email: info.email,
        resendAfter: info.resend_after_seconds,
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
          email={pending.kind === "phone" ? formatPhone(pending.phone) : pending.email}
          resendAfterSeconds={pending.resendAfter}
          reason={
            pending.kind === "phone"
              ? "We sent you a code by SMS."
              : pending.kind === "google"
                ? "To keep your account safe, we check new devices and new Google links with a code."
                : undefined
          }
          onBack={back}
          onVerify={async (code) => {
            try {
              finish(
                pending.kind === "password"
                  ? await verifyNewDevice({ login_ticket: pending.ticket, code })
                  : pending.kind === "google"
                    ? await googleVerify({ id_token: pending.idToken, code })
                    : await verifyPhoneCode(pending.phone, code),
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
              : pending.kind === "phone"
                ? async () => (await requestPhoneCode(pending.phone)).resend_after_seconds
                : undefined
          }
        />
      </AuthLayout>
    );
  }

  const locked = wait.remaining > 0;
  const alerts = (
    <>
      {invited && !error && (
        <FormAlert tone="success">
          <b>Invitation accepted.</b> Log in with your new password.
        </FormAlert>
      )}
      {notice && !invited && !error && <FormAlert tone="info">{notice}</FormAlert>}
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
    </>
  );
  const switchTo = (next: Method) => {
    setError(null);
    setMethod(next);
  };

  if (method === "phone") {
    return (
      <AuthLayout>
        <BackToChoices onClick={() => switchTo("choose")} />
        <AuthHeading title="Log in with your phone" subtitle="We'll send a code by SMS." />
        {alerts}
        <PhoneForm
          locked={locked}
          onSent={(phone, resendAfter) => setPending({ kind: "phone", phone, resendAfter })}
          onError={handleError}
        />
        <Footer />
      </AuthLayout>
    );
  }

  if (method === "email") {
    return (
      <AuthLayout>
        {!invited && <BackToChoices onClick={() => switchTo("choose")} />}
        <AuthHeading
          title="Log in with email"
          subtitle="Use the email the institute has for you."
        />
        {alerts}
        <form onSubmit={onPassword} className="flex flex-col gap-4" noValidate>
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
              <PasswordInput
                {...p}
                {...form.register("password")}
                autoComplete="current-password"
                autoFocus={invited}
              />
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
          New devices are checked with a code sent to your email.
        </p>
        <Footer />
      </AuthLayout>
    );
  }

  const showGoogle = !!GOOGLE_CLIENT_ID && methods.data?.google !== false;
  return (
    <AuthLayout>
      <AuthHeading title="Log in" subtitle="Choose how you'd like to log in." />
      {alerts}
      <div className="flex flex-col gap-3">
        {showGoogle && <GoogleButton onCredential={(token) => void onGoogle(token)} />}
        <ChoiceButton
          icon={<MailIcon className="size-5" aria-hidden="true" />}
          onClick={() => switchTo("email")}
        >
          Continue with email
        </ChoiceButton>
        {methods.data?.phone && (
          <ChoiceButton
            icon={<SmartphoneIcon className="size-5" aria-hidden="true" />}
            onClick={() => switchTo("phone")}
          >
            Continue with phone
          </ChoiceButton>
        )}
      </div>
      <p className="text-center text-xs leading-relaxed text-muted">
        Logins are created by the institute. Use the email or phone number you gave them.
      </p>
      <Footer />
    </AuthLayout>
  );
}

function ChoiceButton({
  icon,
  onClick,
  children,
}: {
  icon: ReactNode;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      onClick={onClick}
      className="justify-center gap-2.5"
    >
      {icon}
      {children}
    </Button>
  );
}

function BackToChoices({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="-mb-2 flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
    >
      <ArrowLeftIcon className="size-4" aria-hidden="true" /> Other ways to log in
    </button>
  );
}

function PhoneForm({
  locked,
  onSent,
  onError,
}: {
  locked: boolean;
  onSent: (phone: string, resendAfter: number) => void;
  onError: (err: unknown) => void;
}) {
  const [phone, setPhone] = useState("");
  const [invalid, setInvalid] = useState<string | undefined>();
  const [sending, setSending] = useState(false);

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        const value = phone.trim();
        if (!/^\+?[\d\s-]{10,16}$/.test(value))
          return setInvalid("Enter a 10-digit mobile number.");
        setInvalid(undefined);
        setSending(true);
        requestPhoneCode(value)
          .then((r) => onSent(value, r.resend_after_seconds))
          .catch(onError)
          .finally(() => setSending(false));
      }}
    >
      <FormField label="Mobile number" error={invalid}>
        {(p) => (
          <Input
            {...p}
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="98765 43210"
          />
        )}
      </FormField>
      <Button type="submit" size="lg" disabled={sending || locked}>
        {sending ? "Sending…" : "Send code"}
      </Button>
    </form>
  );
}

function Footer() {
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-4 text-center text-sm">
      <p>
        New to Sai Personal Tuitions?{" "}
        <Link to="/enquire" className="font-bold text-primary hover:underline">
          Ask about admission
        </Link>
      </p>
      <p className="flex items-center justify-center gap-2 text-xs text-muted">
        <Link to="/privacy" className="hover:text-ink hover:underline">
          Privacy Policy
        </Link>
        <span aria-hidden="true">·</span>
        <Link to="/terms" className="hover:text-ink hover:underline">
          Terms of Use
        </Link>
      </p>
    </div>
  );
}
