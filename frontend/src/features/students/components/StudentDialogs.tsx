/**
 * The profile's change dialogs: personal details, class (board/standard/
 * school, recorded in the academic history with a reason) and status.
 */
import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { ReferenceSelect } from "@/features/academics";
import { ApiError } from "@/lib/api/envelope";
import { MEDIUM_OPTIONS } from "@/lib/options";
import type { StudentDetail, StudentStatus } from "@/lib/api/types";

import {
  CHANGE_REASONS,
  GENDER_OPTIONS,
  STATUS_OPTIONS,
  useChangeAcademic,
  useSetStudentStatus,
  useUpdateStudent,
} from "../api";

type DialogProps = { student: StudentDetail; open: boolean; onOpenChange: (open: boolean) => void };

function Footer({ pending, label }: { pending: boolean; label: string }) {
  return (
    <div className="col-span-full flex justify-end gap-2.5 pt-1">
      <DialogClose asChild>
        <Button variant="secondary" disabled={pending}>
          Cancel
        </Button>
      </DialogClose>
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : label}
      </Button>
    </div>
  );
}

const fieldErrors = (err: unknown) =>
  err instanceof ApiError
    ? Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v.join(" ")]))
    : {};

const PERSONAL = [
  "first_name",
  "last_name",
  "date_of_birth",
  "gender",
  "medium",
  "address",
  "guardian_name",
  "guardian_relation",
  "guardian_phone",
  "guardian_email",
  "remarks",
] as const;
type Personal = Record<(typeof PERSONAL)[number], string>;

export function EditDetailsDialog({ student, open, onOpenChange }: DialogProps) {
  const update = useUpdateStudent(student.id);
  const [values, setValues] = useState<Personal>(
    () =>
      Object.fromEntries(PERSONAL.map((k) => [k, (student[k] as string | null) ?? ""])) as Personal,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const bind = (key: keyof Personal) => ({
    value: values[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value })),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const body = Object.fromEntries(
      PERSONAL.map((k) => [k, k === "date_of_birth" ? values[k] || null : values[k].trim()]),
    );
    update.mutate(body, {
      onSuccess: () => {
        toast.success("Details saved.");
        onOpenChange(false);
      },
      onError: (err) => {
        const errs = fieldErrors(err);
        setErrors(errs);
        if (!Object.keys(errs).length) toast.error(err.message);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !update.isPending && onOpenChange(o)}>
      <DialogContent title="Edit details" className="max-w-2xl">
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
          <FormField label="First name" error={errors.first_name}>
            {(p) => <Input {...p} {...bind("first_name")} />}
          </FormField>
          <FormField label="Last name" error={errors.last_name}>
            {(p) => <Input {...p} {...bind("last_name")} />}
          </FormField>
          <FormField label="Date of birth" error={errors.date_of_birth}>
            {(p) => <Input {...p} type="date" {...bind("date_of_birth")} />}
          </FormField>
          <FormField label="Gender">
            {(p) => (
              <NativeSelect {...p} {...bind("gender")}>
                <option value="">Not given</option>
                {GENDER_OPTIONS.map((g) => (
                  <option key={g.value} value={g.value}>
                    {g.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Medium (optional)">
            {(p) => (
              <NativeSelect {...p} {...bind("medium")}>
                <option value="">Not given</option>
                {MEDIUM_OPTIONS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Guardian name" error={errors.guardian_name}>
            {(p) => <Input {...p} {...bind("guardian_name")} />}
          </FormField>
          <FormField label="Relation">
            {(p) => <Input {...p} {...bind("guardian_relation")} />}
          </FormField>
          <FormField label="Guardian phone" error={errors.guardian_phone}>
            {(p) => <Input {...p} type="tel" {...bind("guardian_phone")} />}
          </FormField>
          <FormField label="Guardian email" error={errors.guardian_email}>
            {(p) => <Input {...p} type="email" {...bind("guardian_email")} />}
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="Address">
              {(p) => <Textarea {...p} rows={2} {...bind("address")} />}
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="Remarks">
              {(p) => <Textarea {...p} rows={2} {...bind("remarks")} />}
            </FormField>
          </div>
          <Footer pending={update.isPending} label="Save" />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ChangeClassDialog({ student, open, onOpenChange }: DialogProps) {
  const change = useChangeAcademic(student.id);
  const [board, setBoard] = useState(String(student.board.id));
  const [standard, setStandard] = useState(String(student.standard.id));
  const [school, setSchool] = useState(String(student.school.id));
  const [reason, setReason] = useState("PROMOTION");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const body: { reason: string; board?: number; standard?: number; school?: number } = { reason };
    if (Number(board) !== student.board.id) body.board = Number(board);
    if (Number(standard) !== student.standard.id) body.standard = Number(standard);
    if (Number(school) !== student.school.id) body.school = Number(school);
    if (!body.board && !body.standard && !body.school) {
      setError("Change the board, standard or school first.");
      return;
    }
    change.mutate(body, {
      onSuccess: () => {
        toast.success("Class changed. The change is recorded in the academic history.");
        onOpenChange(false);
      },
      onError: (err) => setError(err.message),
    });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !change.isPending && onOpenChange(o)}>
      <DialogContent
        title="Change class"
        description="For promotions, repeats and school or board changes. Fees for a new year are set up in Fees → year-end rollover."
      >
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {error && (
            <p className="rounded-[var(--radius-control)] bg-danger-bg px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
          <FormField label="Board">
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="boards"
                value={board}
                onChange={(e) => setBoard(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Standard">
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="standards"
                value={standard}
                onChange={(e) => setStandard(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="School">
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="schools"
                value={school}
                onChange={(e) => setSchool(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Why">
            {(p) => (
              <NativeSelect {...p} value={reason} onChange={(e) => setReason(e.target.value)}>
                {CHANGE_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <Footer pending={change.isPending} label="Change class" />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ChangeStatusDialog({ student, open, onOpenChange }: DialogProps) {
  const setStatus = useSetStudentStatus(student.id);
  const [status, setValue] = useState<StudentStatus>(student.status ?? "ACTIVE");
  return (
    <Dialog open={open} onOpenChange={(o) => !setStatus.isPending && onOpenChange(o)}>
      <DialogContent
        title="Change status"
        description="A student who left or completed keeps all their records; their parents can still log in to see them."
      >
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setStatus.mutate(status, {
              onSuccess: () => {
                toast.success("Status changed.");
                onOpenChange(false);
              },
              onError: (err) => toast.error(err.message),
            });
          }}
        >
          <FormField label="Status">
            {(p) => (
              <NativeSelect
                {...p}
                value={status}
                onChange={(e) => setValue(e.target.value as StudentStatus)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <Footer pending={setStatus.isPending} label="Save" />
        </form>
      </DialogContent>
    </Dialog>
  );
}
