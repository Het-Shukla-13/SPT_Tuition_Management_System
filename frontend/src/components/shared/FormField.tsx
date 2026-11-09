import { type ReactNode, useId } from "react";

import { Label } from "@/components/ui/input";

/**
 * Label + control + hint + error, wired for screen readers. The control is a
 * render prop so it receives the right id/aria attributes:
 *
 *   <FormField label="Amount (₹)" error={errors.amount?.message}>
 *     {(props) => <Input {...props} {...register("amount")} />}
 *   </FormField>
 *
 * Server field errors (VALIDATION_ERROR) are shown here too, via setError.
 */
export function FormField({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: ReactNode;
  error?: string;
  children: (props: {
    id: string;
    "aria-invalid"?: true;
    "aria-describedby"?: string;
  }) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy })}
      {hint && !error && (
        <span id={hintId} className="text-xs text-muted">
          {hint}
        </span>
      )}
      {error && (
        <span id={errorId} className="text-[13px] text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
