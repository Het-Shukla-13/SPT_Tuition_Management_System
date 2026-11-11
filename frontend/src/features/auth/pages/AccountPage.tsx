import { zodResolver } from "@hookform/resolvers/zod";
import { LaptopIcon, LogOutIcon } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/envelope";
import { session } from "@/lib/api/session";
import { formatAgo, formatDate, formatPhone } from "@/lib/format";

import {
  useChangePassword,
  useRemoveDevice,
  useRevokeSession,
  useSessions,
  useTrustedDevices,
} from "../api";
import { describeAgent } from "../describeAgent";
import { displayName, ROLE_LABEL, useCurrentUser, useLogout } from "../session";

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    new_password: z.string().min(8, "Use at least 8 characters."),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    message: "The passwords don't match.",
    path: ["confirm"],
  });

/** My account: details, password, trusted devices, logged-in sessions. */
export function AccountPage() {
  const user = useCurrentUser();
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="My account" eyebrow={ROLE_LABEL[user.role]} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,380px),1fr))] gap-5">
        <Card>
          <CardHeader title="Details" />
          <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
            <dt className="text-muted">Name</dt>
            <dd className="font-bold">{displayName(user)}</dd>
            <dt className="text-muted">Email</dt>
            <dd className="font-bold break-all">{user.email ?? "–"}</dd>
            <dt className="text-muted">Phone</dt>
            <dd className="font-bold">{formatPhone(user.phone)}</dd>
            <dt className="text-muted">Google</dt>
            <dd className="font-bold">{user.google_linked ? "Linked" : "Not linked"}</dd>
          </dl>
          <p className="text-xs text-muted">To change your name, ask the institute office.</p>
        </Card>
        <ChangePasswordCard />
      </div>
      <DevicesCard />
      <SessionsCard />
    </div>
  );
}

function ChangePasswordCard() {
  const change = useChangePassword();
  const form = useForm({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  const onSubmit = form.handleSubmit(async ({ current_password, new_password }) => {
    try {
      await change.mutateAsync({ current_password, new_password });
      form.reset();
      toast.success("Password changed. Your other devices were logged out.");
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      if (err.code === "WRONG_PASSWORD")
        form.setError("current_password", { message: err.message });
      else if (err.fieldErrors.new_password)
        form.setError("new_password", { message: err.fieldErrors.new_password.join(" ") });
      else toast.error(err.message);
    }
  });

  return (
    <Card>
      <CardHeader title="Change password" />
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormField label="Current password" error={form.formState.errors.current_password?.message}>
          {(p) => (
            <PasswordInput
              {...p}
              {...form.register("current_password")}
              autoComplete="current-password"
            />
          )}
        </FormField>
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
        <Button type="submit" disabled={form.formState.isSubmitting} className="self-start">
          {form.formState.isSubmitting ? "Saving…" : "Change password"}
        </Button>
        <p className="text-xs text-muted">
          Your other devices will be logged out and asked for a code next time.
        </p>
      </form>
    </Card>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </div>
  );
}

function DevicesCard() {
  const devices = useTrustedDevices();
  const remove = useRemoveDevice();
  return (
    <Card>
      <CardHeader title="Trusted devices" />
      <p className="-mt-2 text-sm text-muted">
        These devices skip the emailed code when you log in, for 90 days. Remove one you don't
        recognise or no longer use.
      </p>
      {devices.isPending ? (
        <ListSkeleton />
      ) : devices.error ? (
        <ErrorState error={devices.error} onRetry={() => void devices.refetch()} />
      ) : devices.data.length === 0 ? (
        <p className="text-sm text-muted">No trusted devices.</p>
      ) : (
        <ul className="flex flex-col">
          {devices.data.map((device) => (
            <li
              key={device.id}
              className="flex flex-wrap items-center justify-between gap-3 border-t border-line/70 py-3 first:border-t-0"
            >
              <span className="flex min-w-0 items-center gap-3">
                <LaptopIcon className="size-5 shrink-0 text-muted" aria-hidden="true" />
                <span className="flex min-w-0 flex-col">
                  <span className="font-bold">
                    {describeAgent(device.label)}{" "}
                    {device.is_current && <Badge tone="brand">This device</Badge>}
                  </span>
                  <span className="text-[13px] text-muted">
                    Last used {formatAgo(device.last_used_at)} · trusted until{" "}
                    {formatDate(device.expires_at)}
                  </span>
                </span>
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(device.id, {
                    onSuccess: () =>
                      toast.success("Device removed. It will need a code next time."),
                    onError: (e) => toast.error(e.message),
                  })
                }
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SessionsCard() {
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const logout = useLogout();
  const navigate = useNavigate();
  const [confirmAll, setConfirmAll] = useState(false);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const logoutAll = async () => {
    setLoggingOutAll(true);
    try {
      await api.post("auth/logout-all/");
    } finally {
      session.clear("LOGGED_OUT");
      navigate("/login", { replace: true });
    }
  };

  return (
    <Card>
      <CardHeader
        title="Where you're logged in"
        action={
          <Button variant="secondary" size="sm" onClick={() => setConfirmAll(true)}>
            Log out everywhere
          </Button>
        }
      />
      {sessions.isPending ? (
        <ListSkeleton />
      ) : sessions.error ? (
        <ErrorState error={sessions.error} onRetry={() => void sessions.refetch()} />
      ) : (
        <ul className="flex flex-col">
          {sessions.data.map((s) => (
            <li
              key={s.id}
              className="flex flex-wrap items-center justify-between gap-3 border-t border-line/70 py-3 first:border-t-0"
            >
              <span className="flex min-w-0 flex-col">
                <span className="font-bold">
                  {describeAgent(s.user_agent)}{" "}
                  {s.is_current && <Badge tone="brand">This device</Badge>}
                </span>
                <span className="text-[13px] text-muted">
                  Active {formatAgo(s.last_active_at)} · since {formatDate(s.created_at)}
                </span>
              </span>
              {s.is_current ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={logout.isPending}
                  onClick={() =>
                    logout.mutate(undefined, {
                      onSettled: () => navigate("/login", { replace: true }),
                    })
                  }
                >
                  <LogOutIcon aria-hidden="true" /> Log out
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={revoke.isPending}
                  onClick={() =>
                    revoke.mutate(s.id, {
                      onSuccess: () => toast.success("That device was logged out."),
                      onError: (e) => toast.error(e.message),
                    })
                  }
                >
                  Log out
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={confirmAll}
        onOpenChange={setConfirmAll}
        title="Log out everywhere?"
        description="Every device, this one included, is logged out and will need your password and an emailed code next time."
        confirmLabel="Log out everywhere"
        pending={loggingOutAll}
        onConfirm={() => void logoutAll()}
      />
    </Card>
  );
}
