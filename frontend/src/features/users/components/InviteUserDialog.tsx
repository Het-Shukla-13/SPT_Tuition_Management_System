import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { useCurrentUser } from "@/features/auth/session";
import { ApiError } from "@/lib/api/envelope";
import type { Role } from "@/lib/api/types";

import { useInviteUser } from "../api";

const schema = z.object({
  role: z.enum(["TEACHER", "ADMIN"]),
  first_name: z.string().trim().min(1, "Enter the first name."),
  last_name: z.string().trim().min(1, "Enter the last name."),
  email: z.email("Enter a valid email address."),
  phone: z.string().trim().optional(),
});
type Values = z.infer<typeof schema>;

/**
 * Invite a teacher or (owner only) an admin. Parents and students are added
 * from the admission form instead, together with their student.
 */
export function InviteUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const me = useCurrentUser();
  const invite = useInviteUser();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { role: "TEACHER", first_name: "", last_name: "", email: "", phone: "" },
  });
  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const result = await invite.mutateAsync({
        ...values,
        role: values.role as Role,
        phone: values.phone || undefined,
      });
      const sent = Object.values(result.invite_sent as Record<string, boolean>).some(Boolean);
      toast.success(
        sent
          ? `Invite sent to ${values.email}. They set their own password from the email.`
          : `Login created, but the invite email couldn't be sent. Use "Resend invite" later.`,
      );
      form.reset();
      onOpenChange(false);
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      let fieldError = false;
      for (const [field, messages] of Object.entries(err.fieldErrors)) {
        if (field in schema.shape) {
          form.setError(field as keyof Values, { message: messages.join(" ") });
          fieldError = true;
        }
      }
      if (!fieldError) toast.error(err.message);
    }
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !invite.isPending && onOpenChange(next)}>
      <DialogContent
        title="Invite staff"
        description="They get an email to set their own password. The office never sees passwords."
      >
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormField
            label="Role"
            hint={me.is_owner ? undefined : "Only the owner can invite admins."}
            error={errors.role?.message}
          >
            {(p) => (
              <NativeSelect {...p} {...form.register("role")}>
                <option value="TEACHER">Teacher</option>
                {me.is_owner && <option value="ADMIN">Admin</option>}
              </NativeSelect>
            )}
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="First name" error={errors.first_name?.message}>
              {(p) => <Input {...p} {...form.register("first_name")} autoComplete="off" />}
            </FormField>
            <FormField label="Last name" error={errors.last_name?.message}>
              {(p) => <Input {...p} {...form.register("last_name")} autoComplete="off" />}
            </FormField>
          </div>
          <FormField label="Email" error={errors.email?.message}>
            {(p) => (
              <Input
                {...p}
                {...form.register("email")}
                type="email"
                inputMode="email"
                autoComplete="off"
              />
            )}
          </FormField>
          <FormField label="Phone (optional)" error={errors.phone?.message}>
            {(p) => (
              <Input
                {...p}
                {...form.register("phone")}
                type="tel"
                inputMode="tel"
                autoComplete="off"
              />
            )}
          </FormField>
          <div className="flex justify-end gap-2.5 pt-1">
            <DialogClose asChild>
              <Button variant="secondary" disabled={invite.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={invite.isPending}>
              {invite.isPending ? "Sending…" : "Send invite"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
