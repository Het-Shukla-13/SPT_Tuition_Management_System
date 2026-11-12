import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormField } from "@/components/shared/FormField";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import type { LinkedLogin, StudentDetail } from "@/lib/api/types";
import { formatPhone } from "@/lib/format";

import { studentName, useGrantAccess, useRevokeAccess } from "../api";
import { ExistingLoginPicker } from "./ExistingLoginPicker";

/** Who can log in to see this student: link a new or existing login, or remove one. */
export function LoginsCard({ student }: { student: StudentDetail }) {
  const logins = student.logins as unknown as LinkedLogin[];
  const revoke = useRevokeAccess(student.id);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<LinkedLogin | null>(null);

  return (
    <Card>
      <CardHeader
        title={`Who can see ${student.first_name}`}
        action={
          <Button variant="ghost" size="sm" onClick={() => setAdding(true)}>
            + Link a login
          </Button>
        }
      />
      {logins.length === 0 ? (
        <p className="text-sm text-muted">Nobody can log in to see this student yet.</p>
      ) : (
        <ul className="flex flex-col">
          {logins.map((login) => (
            <li
              key={login.user_id}
              className="flex flex-wrap items-center justify-between gap-3 border-t border-line/70 py-3 first:border-t-0"
            >
              <span className="flex min-w-0 flex-col">
                <span className="font-bold">
                  {login.first_name} {login.last_name}
                  {!login.invite_accepted && (
                    <Badge tone="info" className="ml-2">
                      Invited
                    </Badge>
                  )}
                </span>
                <span className="truncate text-[13px] text-muted">
                  {[login.email, login.phone && formatPhone(login.phone)]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="text-danger"
                onClick={() => setRemoving(login)}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      {adding && <LinkLoginDialog student={student} onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title="Remove this login's access?"
        description={
          removing
            ? `${removing.first_name} ${removing.last_name} will no longer see ${studentName(student)}. Their login stays (they may see other children).`
            : undefined
        }
        confirmLabel="Remove access"
        pending={revoke.isPending}
        onConfirm={() =>
          removing &&
          revoke.mutate(removing.user_id, {
            onSuccess: () => {
              setRemoving(null);
              toast.success("Access removed.");
            },
            onError: (e) => {
              setRemoving(null);
              toast.error(e.message);
            },
          })
        }
      />
    </Card>
  );
}

const newLoginSchema = z.object({
  first_name: z.string().trim().min(1, "Enter the first name."),
  last_name: z.string().trim().min(1, "Enter the last name."),
  email: z.email("Enter the email they'll log in with."),
  phone: z.string(),
});

function LinkLoginDialog({ student, onClose }: { student: StudentDetail; onClose: () => void }) {
  const grant = useGrantAccess(student.id);
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const form = useForm({
    resolver: zodResolver(newLoginSchema),
    defaultValues: { first_name: "", last_name: "", email: "", phone: "" },
  });
  const already = (student.logins as unknown as LinkedLogin[]).map((l) => l.user_id);

  const done = (message: string) => {
    toast.success(message);
    onClose();
  };
  const failed = (err: Error) => {
    if (err instanceof ApiError) {
      const errs = (err.errors as { new_login?: Record<string, string[]> } | null)?.new_login ?? {};
      for (const [k, v] of Object.entries(errs))
        form.setError(k as never, { message: v.join(" ") });
      if (!Object.keys(errs).length) toast.error(err.message);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && !grant.isPending && onClose()}>
      <DialogContent title={`Link a login to ${student.first_name}`}>
        <div className="flex gap-2" role="tablist">
          {(["existing", "new"] as const).map((m) => (
            <Button
              key={m}
              role="tab"
              aria-selected={mode === m}
              variant={mode === m ? "primary" : "secondary"}
              size="sm"
              onClick={() => setMode(m)}
            >
              {m === "existing" ? "Existing login" : "New login"}
            </Button>
          ))}
        </div>
        {mode === "existing" ? (
          <ExistingLoginPicker
            exclude={already}
            onPick={(user) =>
              grant.mutate(
                { user_id: user.id },
                { onSuccess: () => done("Login linked."), onError: failed },
              )
            }
          />
        ) : (
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={form.handleSubmit((v) =>
              grant.mutate(
                { new_login: { ...v, phone: v.phone.trim() || undefined } },
                {
                  onSuccess: () => done(`Login created. Invite sent to ${v.email}.`),
                  onError: failed,
                },
              ),
            )}
          >
            <div className="grid grid-cols-2 gap-3">
              <FormField label="First name" error={form.formState.errors.first_name?.message}>
                {(p) => <Input {...p} {...form.register("first_name")} />}
              </FormField>
              <FormField label="Last name" error={form.formState.errors.last_name?.message}>
                {(p) => <Input {...p} {...form.register("last_name")} />}
              </FormField>
            </div>
            <FormField
              label="Email"
              hint="They log in with this."
              error={form.formState.errors.email?.message}
            >
              {(p) => <Input {...p} {...form.register("email")} type="email" />}
            </FormField>
            <FormField label="Phone (optional)" error={form.formState.errors.phone?.message}>
              {(p) => <Input {...p} {...form.register("phone")} type="tel" />}
            </FormField>
            <div className="flex justify-end gap-2.5">
              <DialogClose asChild>
                <Button variant="secondary">Cancel</Button>
              </DialogClose>
              <Button type="submit" disabled={grant.isPending}>
                {grant.isPending ? "Creating…" : "Create & invite"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
