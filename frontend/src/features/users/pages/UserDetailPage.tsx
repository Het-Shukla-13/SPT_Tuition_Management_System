import { type ReactNode, useState } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { displayName, ROLE_LABEL, useCurrentUser } from "@/features/auth/session";
import { ApiError } from "@/lib/api/envelope";
import type { AdminUser, Role } from "@/lib/api/types";
import { formatAgo, formatDate, formatPhone } from "@/lib/format";

import {
  ROLE_OPTIONS,
  useChangeRole,
  useResendInvite,
  useSetActive,
  useSetContact,
  userStatus,
  useUpdateName,
  useUser,
} from "../api";

const errorMessage = (err: unknown) =>
  err instanceof ApiError ? err.message : "Something went wrong.";

/** One login: details and every admin action, each guarded the way the backend is. */
export function UserDetailPage() {
  const id = Number(useParams().id);
  const user = useUser(id);
  const me = useCurrentUser();

  if (user.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (user.error) return <ErrorState error={user.error} onRetry={() => void user.refetch()} />;

  const u = user.data;
  const self = u.id === me.id;
  // Mirrors the backend: only an owner may change another admin, and nobody
  // changes an owner account but that owner (from their own account page).
  const canManage =
    !self && (!(u.role === "ADMIN" || u.is_superuser) || me.is_owner) && !u.is_superuser;

  return (
    <>
      <PageHeader
        back={{ to: "/staff/users", label: "Users & invites" }}
        title={displayName(u)}
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            {ROLE_LABEL[u.role]} <StatusBadge status={userStatus(u)} />
            {u.is_superuser && <Badge tone="brand">Owner</Badge>}
          </span>
        }
      />
      {self && (
        <p className="text-sm text-muted">This is you. Change your own details from My account.</p>
      )}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,380px),1fr))] gap-5">
        <Card>
          <CardHeader title="Details" action={canManage && <EditNameButton user={u} />} />
          <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
            <Row label="Email" value={u.email ?? "–"} verified={!!u.email_verified_at} />
            <Row label="Phone" value={formatPhone(u.phone)} verified={!!u.phone_verified_at} />
            <Row
              label="Invite"
              value={
                u.invite_accepted ? `Accepted ${formatDate(u.activated_at)}` : "Not logged in yet"
              }
            />
            <Row label="Last login" value={u.last_login ? formatAgo(u.last_login) : "Never"} />
            <Row label="Created" value={formatDate(u.created_at)} />
          </dl>
        </Card>
        {canManage && <ActionsCard user={u} />}
        {!self && u.is_superuser && (
          <p className="text-sm text-muted">
            This is an owner account. Only that owner can change it, from their own account page.
          </p>
        )}
      </div>
    </>
  );
}

function Row({ label, value, verified }: { label: string; value: ReactNode; verified?: boolean }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="font-bold break-all">
        {value}
        {verified && (
          <Badge tone="success" className="ml-2">
            Verified
          </Badge>
        )}
      </dd>
    </>
  );
}

function ActionsCard({ user }: { user: AdminUser }) {
  const me = useCurrentUser();
  const setActive = useSetActive(user.id);
  const resend = useResendInvite(user.id);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  return (
    <Card>
      <CardHeader title="Actions" />
      <div className="flex flex-col gap-3">
        {!user.invite_accepted && user.is_active && (
          <Action
            title="Resend invite"
            description="Emails them again how to set their password."
            button={
              <Button
                variant="secondary"
                size="sm"
                disabled={resend.isPending}
                onClick={() =>
                  resend.mutate(undefined, {
                    onSuccess: () => toast.success("Invite sent again."),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                Resend
              </Button>
            }
          />
        )}
        <Action
          title="Fix email or phone"
          description="If they lost access to their email/phone. The new one is verified at their next login."
          button={<ContactButton user={user} />}
        />
        {me.is_owner && (
          <Action
            title="Change role"
            description="Logs them out everywhere."
            button={<RoleButton user={user} />}
          />
        )}
        {user.is_active ? (
          <Action
            title="Deactivate"
            description="They're logged out everywhere and can't log in. Their records stay."
            button={
              <Button variant="danger" size="sm" onClick={() => setConfirmDeactivate(true)}>
                Deactivate
              </Button>
            }
          />
        ) : (
          <Action
            title="Reactivate"
            description="They can log in again."
            button={
              <Button
                size="sm"
                disabled={setActive.isPending}
                onClick={() =>
                  setActive.mutate(true, {
                    onSuccess: () => toast.success("Login reactivated."),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                Reactivate
              </Button>
            }
          />
        )}
      </div>
      <ConfirmDialog
        open={confirmDeactivate}
        onOpenChange={setConfirmDeactivate}
        title={`Deactivate ${displayName(user)}?`}
        description="They're logged out on every device right away and can't log in until reactivated."
        confirmLabel="Deactivate"
        pending={setActive.isPending}
        onConfirm={() =>
          setActive.mutate(false, {
            onSuccess: () => {
              setConfirmDeactivate(false);
              toast.success("Login deactivated.");
            },
            onError: (e) => {
              setConfirmDeactivate(false);
              toast.error(errorMessage(e));
            },
          })
        }
      />
    </Card>
  );
}

function Action({
  title,
  description,
  button,
}: {
  title: string;
  description: string;
  button: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/70 pt-3 first:border-t-0 first:pt-0">
      <span className="flex max-w-sm flex-col">
        <span className="font-bold">{title}</span>
        <span className="text-[13px] text-muted">{description}</span>
      </span>
      {button}
    </div>
  );
}

function EditNameButton({ user }: { user: AdminUser }) {
  const update = useUpdateName(user.id);
  const [open, setOpen] = useState(false);
  const [first, setFirst] = useState(user.first_name);
  const [last, setLast] = useState(user.last_name);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        Edit name
      </Button>
      <DialogContent title="Edit name">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate(
              { first_name: first.trim(), last_name: last.trim() },
              {
                onSuccess: () => (setOpen(false), toast.success("Name updated.")),
                onError: (err) => toast.error(errorMessage(err)),
              },
            );
          }}
        >
          <FormField label="First name">
            {(p) => <Input {...p} value={first} onChange={(e) => setFirst(e.target.value)} />}
          </FormField>
          <FormField label="Last name">
            {(p) => <Input {...p} value={last} onChange={(e) => setLast(e.target.value)} />}
          </FormField>
          <DialogFooter pending={update.isPending} label="Save" />
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RoleButton({ user }: { user: AdminUser }) {
  const change = useChangeRole(user.id);
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<Role>(user.role);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        Change
      </Button>
      <DialogContent
        title="Change role"
        description="The change applies at once and logs them out everywhere."
      >
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            change.mutate(role, {
              onSuccess: () => (setOpen(false), toast.success("Role changed.")),
              onError: (err) => toast.error(errorMessage(err)),
            });
          }}
        >
          <FormField label="Role">
            {(p) => (
              <NativeSelect {...p} value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <DialogFooter
            pending={change.isPending}
            label="Change role"
            disabled={role === user.role}
          />
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ContactButton({ user }: { user: AdminUser }) {
  const setContact = useSetContact(user.id);
  const [open, setOpen] = useState(false);
  const [channel, setChannel] = useState<"EMAIL" | "PHONE">("EMAIL");
  const [value, setValue] = useState("");
  const current = channel === "EMAIL" ? user.email : user.phone;
  const save = (identifier: string | null) =>
    setContact.mutate(
      { channel, identifier },
      {
        onSuccess: () => {
          setOpen(false);
          setValue("");
          toast.success(identifier ? "Saved. It's verified at their next login." : "Removed.");
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        Fix
      </Button>
      <DialogContent
        title="Fix email or phone"
        description="Use this when someone lost access to their email or phone."
      >
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save(value.trim());
          }}
        >
          <FormField label="Which one">
            {(p) => (
              <NativeSelect
                {...p}
                value={channel}
                onChange={(e) => setChannel(e.target.value as "EMAIL" | "PHONE")}
              >
                <option value="EMAIL">Email</option>
                <option value="PHONE">Phone</option>
              </NativeSelect>
            )}
          </FormField>
          <p className="text-sm text-muted">
            Now: {current ? (channel === "PHONE" ? formatPhone(current) : current) : "none"}
          </p>
          <FormField label={channel === "EMAIL" ? "New email" : "New phone"}>
            {(p) => (
              <Input
                {...p}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                type={channel === "EMAIL" ? "email" : "tel"}
                inputMode={channel === "EMAIL" ? "email" : "tel"}
              />
            )}
          </FormField>
          <div className="flex flex-wrap justify-between gap-2.5">
            {current ? (
              <Button variant="ghost" disabled={setContact.isPending} onClick={() => save(null)}>
                Remove current
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2.5">
              <DialogClose asChild>
                <Button variant="secondary">Cancel</Button>
              </DialogClose>
              <Button type="submit" disabled={setContact.isPending || !value.trim()}>
                Save
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DialogFooter({
  pending,
  label,
  disabled,
}: {
  pending: boolean;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex justify-end gap-2.5 pt-1">
      <DialogClose asChild>
        <Button variant="secondary" disabled={pending}>
          Cancel
        </Button>
      </DialogClose>
      <Button type="submit" disabled={pending || disabled}>
        {pending ? "Saving…" : label}
      </Button>
    </div>
  );
}
