import { Money } from "@/components/shared/Money";
import { Input } from "@/components/ui/input";

import type { ExtraChoice, optionalSubjectRows } from "../optionalSubjects";

/**
 * Admission: each optional subject the student takes that has its own fee, ticked
 * by default with the structure's amount. Staff can change the amount or waive it.
 */
export function OptionalSubjectFees({
  rows,
  onChange,
  error,
}: {
  rows: ReturnType<typeof optionalSubjectRows>;
  onChange: (subject: number, choice: ExtraChoice) => void;
  error?: string;
}) {
  if (rows.length === 0) return null;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-[13px] font-bold">Optional subject fees</legend>
      <p className="text-xs text-muted">
        Added to the fee as separate lines. Untick to waive one, or change the amount.
      </p>
      {rows.map((r) => (
        <div key={r.subject} className="flex flex-wrap items-center gap-3">
          <label className="flex min-w-48 items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={r.choice.on}
              onChange={(e) => onChange(r.subject, { ...r.choice, on: e.target.checked })}
              className="size-4 accent-primary"
            />
            {r.subject_name}
          </label>
          <span className="flex items-center gap-1 text-sm">
            ₹
            <Input
              aria-label={`${r.subject_name} fee`}
              inputMode="decimal"
              value={r.choice.amount}
              disabled={!r.choice.on}
              onChange={(e) => onChange(r.subject, { ...r.choice, amount: e.target.value.trim() })}
              className="w-28 text-right"
            />
          </span>
          <span className="text-xs text-muted">
            usual: <Money value={r.amount} />
          </span>
        </div>
      ))}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}
