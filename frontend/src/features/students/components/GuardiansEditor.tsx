import { XIcon } from "lucide-react";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { emptyGuardian, type GuardianRow, MAX_GUARDIANS } from "../guardians";

/**
 * Up to four guardians (mother, father, ...). The first is the main contact the
 * office calls first. These are contacts on file, not logins.
 */
export function GuardiansEditor({
  value,
  onChange,
  errors = {},
}: {
  value: GuardianRow[];
  onChange: (rows: GuardianRow[]) => void;
  errors?: Record<string, string>;
}) {
  const set = (i: number, patch: Partial<GuardianRow>) =>
    onChange(value.map((g, j) => (j === i ? { ...g, ...patch } : g)));

  return (
    <div className="flex flex-col gap-4">
      {value.map((g, i) => (
        <fieldset
          key={i}
          className="flex flex-col gap-3 rounded-[var(--radius-control)] border border-line p-4"
        >
          <legend className="flex w-full items-center justify-between px-1 text-[13px] font-bold">
            <span>
              {i === 0 ? "Main guardian" : `Guardian ${i + 1}`}
              {i === 0 && (
                <span className="font-semibold text-muted"> · the office calls them first</span>
              )}
            </span>
            {value.length > 1 && (
              <button
                type="button"
                aria-label={`Remove guardian ${i + 1}`}
                onClick={() => onChange(value.filter((_, j) => j !== i))}
                className="flex size-9 items-center justify-center rounded-lg text-muted hover:bg-subtle hover:text-danger"
              >
                <XIcon className="size-4" />
              </button>
            )}
          </legend>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormField label="Name" error={errors[`${i}.name`]}>
              {(p) => (
                <Input
                  {...p}
                  value={g.name}
                  onChange={(e) => set(i, { name: e.target.value })}
                  autoComplete="off"
                />
              )}
            </FormField>
            <FormField
              label="Relation"
              hint={i === 0 ? "e.g. Mother" : "e.g. Father"}
              error={errors[`${i}.relation`]}
            >
              {(p) => (
                <Input
                  {...p}
                  value={g.relation}
                  onChange={(e) => set(i, { relation: e.target.value })}
                  autoComplete="off"
                />
              )}
            </FormField>
            <FormField label="Phone" error={errors[`${i}.phone`]}>
              {(p) => (
                <Input
                  {...p}
                  type="tel"
                  inputMode="tel"
                  value={g.phone}
                  onChange={(e) => set(i, { phone: e.target.value })}
                  autoComplete="off"
                />
              )}
            </FormField>
            <FormField label="Email (optional)" error={errors[`${i}.email`]}>
              {(p) => (
                <Input
                  {...p}
                  type="email"
                  inputMode="email"
                  value={g.email}
                  onChange={(e) => set(i, { email: e.target.value })}
                  autoComplete="off"
                />
              )}
            </FormField>
          </div>
        </fieldset>
      ))}
      {value.length < MAX_GUARDIANS && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="self-start"
          onClick={() => onChange([...value, emptyGuardian()])}
        >
          + Add another guardian
        </Button>
      )}
    </div>
  );
}
