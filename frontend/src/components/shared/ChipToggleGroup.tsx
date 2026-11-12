import { CheckIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type ChipOption = { value: number; label: string };

/**
 * Pick several items by tapping chips (subjects, chapters...). Each chip is
 * a real checkbox for keyboards and screen readers.
 */
export function ChipToggleGroup({
  label,
  options,
  value,
  onChange,
  error,
  loading,
}: {
  label: string;
  options: ChipOption[];
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
  loading?: boolean;
}) {
  const toggle = (id: number) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-[13px] font-bold">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {loading && <span className="text-sm text-muted">Loading…</span>}
        {options.map((option) => {
          const checked = value.includes(option.value);
          return (
            <label
              key={option.value}
              className={cn(
                "inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary",
                checked
                  ? "border-primary bg-primary-tint text-primary"
                  : "border-line-strong bg-surface text-ink hover:bg-subtle",
              )}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={checked}
                onChange={() => toggle(option.value)}
              />
              {checked && <CheckIcon className="size-4" aria-hidden="true" />}
              {option.label}
            </label>
          );
        })}
      </div>
      {error && <span className="text-[13px] text-danger">{error}</span>}
    </fieldset>
  );
}
