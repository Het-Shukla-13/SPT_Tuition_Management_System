import { type FormEvent, type ReactNode, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormField } from "@/components/shared/FormField";
import { OtpInput } from "@/components/shared/OtpInput";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import type { User } from "@/lib/api/types";
import { formatPhone } from "@/lib/format";

import {
  type ContactChannel,
  useRemoveContact,
  useRequestContactChange,
  useUnlinkGoogle,
  useUpdateMyName,
  useVerifyContactChange,
} from "../api";
import { displayName } from "../session";

const message = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong.");

/** Name, email, phone and Google: each person keeps their own details up to date. */
export function MyDetailsCard({ user }: { user: User }) {
  const [editing, setEditing] = useState<"name" | ContactChannel | null>(null);
  const [confirm, setConfirm] = useState<"unlink" | ContactChannel | null>(null);
  const remove = useRemoveContact();
  const unlink = useUnlinkGoogle();
  const hasBoth = !!user.email && !!user.phone;

  return (
    <Card>
      <CardHeader title="My details" />
      <dl className="flex flex-col text-sm">
        <Row label="Name" value={displayName(user)}>
          <Button variant="ghost" size="sm" onClick={() => setEditing("name")}>
            Edit
          </Button>
        </Row>
        <Row label="Email" value={user.email ?? "Not added"}>
          <Button variant="ghost" size="sm" onClick={() => setEditing("EMAIL")}>
            {user.email ? "Change" : "Add"}
          </Button>
          {user.email && hasBoth && (
            <Button
              variant="ghost"
              size="sm"
              className="text-danger"
              onClick={() => setConfirm("EMAIL")}
            >
              Remove
            </Button>
          )}
        </Row>
        <Row label="Phone" value={user.phone ? formatPhone(user.phone) : "Not added"}>
          <Button variant="ghost" size="sm" onClick={() => setEditing("PHONE")}>
            {user.phone ? "Change" : "Add"}
          </Button>
          {user.phone && hasBoth && (
            <Button
              variant="ghost"
              size="sm"
              className="text-danger"
              onClick={() => setConfirm("PHONE")}
            >
              Remove
            </Button>
          )}
        </Row>
        <Row
          label="Google"
          value={
            user.google_linked ? (
              "Linked"
            ) : (
              <span className="font-normal text-muted">
                Not linked. To link it, log out and use “Continue with Google” with{" "}
                {user.email ?? "your Gmail address"}.
              </span>
            )
          }
        >
          {user.google_linked && (
            <Button
              variant="ghost"
              size="sm"
              className="text-danger"
              onClick={() => setConfirm("unlink")}
            >
              Unlink
            </Button>
          )}
        </Row>
      </dl>
      <p className="text-xs text-muted">
        A new email or phone is confirmed with a code sent to it. You can log in with either.
      </p>

      {editing === "name" && <NameDialog user={user} onClose={() => setEditing(null)} />}
      {(editing === "EMAIL" || editing === "PHONE") && (
        <ContactDialog
          channel={editing}
          current={editing === "EMAIL" ? user.email : user.phone}
          onClose={() => setEditing(null)}
        />
      )}
      <ConfirmDialog
        open={confirm === "unlink"}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="Unlink Google?"
        description="“Continue with Google” stops working for this account. You can still log in with your email or phone."
        confirmLabel="Unlink"
        pending={unlink.isPending}
        onConfirm={() =>
          unlink.mutate(undefined, {
            onSuccess: () => {
              setConfirm(null);
              toast.success("Google unlinked.");
            },
            onError: (e) => toast.error(message(e)),
          })
        }
      />
      <ConfirmDialog
        open={confirm === "EMAIL" || confirm === "PHONE"}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={confirm === "EMAIL" ? "Remove your email?" : "Remove your phone?"}
        description={`You'll log in with your ${confirm === "EMAIL" ? "phone" : "email"} only.`}
        confirmLabel="Remove"
        pending={remove.isPending}
        onConfirm={() =>
          confirm !== "unlink" &&
          confirm !== null &&
          remove.mutate(confirm, {
            onSuccess: () => {
              setConfirm(null);
              toast.success("Removed.");
            },
            onError: (e) => toast.error(message(e)),
          })
        }
      />
    </Card>
  );
}

function Row({
  label,
  value,
  children,
}: {
  label: string;
  value: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex min-h-12 flex-wrap items-center gap-x-4 gap-y-1 border-t border-line/70 py-2 first:border-t-0">
      <dt className="w-16 text-muted">{label}</dt>
      <dd className="min-w-0 flex-1 font-bold break-words">{value}</dd>
      {children && <dd className="flex gap-1">{children}</dd>}
    </div>
  );
}

function NameDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const update = useUpdateMyName();
  const [first, setFirst] = useState(user.first_name);
  const [last, setLast] = useState(user.last_name);
  const [error, setError] = useState<string | null>(null);

  const save = (e: FormEvent) => {
    e.preventDefault();
    if (!first.trim()) return setError("Enter your first name.");
    update.mutate(
      { first_name: first.trim(), last_name: last.trim() },
      {
        onSuccess: () => {
          toast.success("Name updated.");
          onClose();
        },
        onError: (err) => setError(message(err)),
      },
    );
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !update.isPending && onClose()}>
      <DialogContent title="Edit name">
        <form onSubmit={save} className="flex flex-col gap-4" noValidate>
          <FormField label="First name" error={error ?? undefined}>
            {(p) => (
              <Input
                {...p}
                value={first}
                onChange={(e) => setFirst(e.target.value)}
                autoComplete="given-name"
              />
            )}
          </FormField>
          <FormField label="Last name">
            {(p) => (
              <Input
                {...p}
                value={last}
                onChange={(e) => setLast(e.target.value)}
                autoComplete="family-name"
              />
            )}
          </FormField>
          <Footer pending={update.isPending} />
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Two steps: the new email/phone, then the code sent to it. */
function ContactDialog({
  channel,
  current,
  onClose,
}: {
  channel: ContactChannel;
  current: string | null | undefined;
  onClose: () => void;
}) {
  const request = useRequestContactChange();
  const verify = useVerifyContactChange();
  const [identifier, setIdentifier] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const email = channel === "EMAIL";
  const what = email ? "email" : "phone number";

  const send = (e?: FormEvent) => {
    e?.preventDefault();
    if (!identifier.trim()) return setError(`Enter the new ${what}.`);
    setError(null);
    request.mutate(
      { channel, identifier: identifier.trim() },
      {
        onSuccess: (r) => {
          setSentTo(r.sent_to);
          setCode("");
        },
        onError: (err) =>
          setError(
            err instanceof ApiError
              ? (err.fieldErrors.identifier?.join(" ") ?? err.message)
              : message(err),
          ),
      },
    );
  };

  const confirm = (e: FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) return setError("Enter the 6-digit code.");
    setError(null);
    verify.mutate(
      { channel, identifier: identifier.trim(), code },
      {
        onSuccess: () => {
          toast.success(email ? "Email updated." : "Phone updated.");
          onClose();
        },
        onError: (err) => setError(message(err)),
      },
    );
  };

  const busy = request.isPending || verify.isPending;
  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent title={`${current ? "Change" : "Add"} ${what}`}>
        {sentTo === null ? (
          <form onSubmit={send} className="flex flex-col gap-4" noValidate>
            {current && (
              <p className="text-sm text-muted">
                Now: <b className="text-ink">{email ? current : formatPhone(current)}</b>
              </p>
            )}
            <FormField label={email ? "New email" : "New mobile number"} error={error ?? undefined}>
              {(p) => (
                <Input
                  {...p}
                  type={email ? "email" : "tel"}
                  inputMode={email ? "email" : "tel"}
                  autoComplete={email ? "email" : "tel"}
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  autoFocus
                />
              )}
            </FormField>
            <Footer pending={request.isPending} label="Send code" />
          </form>
        ) : (
          <form onSubmit={confirm} className="flex flex-col gap-4" noValidate>
            <p className="text-sm">
              We sent a 6-digit code to <b>{sentTo}</b>. Enter it to confirm it's yours.
            </p>
            <OtpInput
              value={code}
              onChange={setCode}
              invalid={!!error}
              disabled={verify.isPending}
              autoFocus
            />
            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => send()}
              >
                Send a new code
              </Button>
              <Footer pending={verify.isPending} label="Confirm" />
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Footer({ pending, label = "Save" }: { pending: boolean; label?: string }) {
  return (
    <div className="flex justify-end gap-2.5">
      <DialogClose asChild>
        <Button variant="secondary" disabled={pending}>
          Cancel
        </Button>
      </DialogClose>
      <Button type="submit" disabled={pending}>
        {pending ? "Please wait…" : label}
      </Button>
    </div>
  );
}
