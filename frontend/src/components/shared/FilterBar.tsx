import { SearchIcon, XIcon } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { Input, Label, NativeSelect } from "@/components/ui/input";

/** The row of search + filters above every list. Wraps on small screens. */
export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <div role="search" className="flex flex-wrap items-center gap-2.5">
      {children}
    </div>
  );
}

/**
 * Search box that waits until typing pauses (300 ms) before searching, so
 * the server isn't asked on every key press.
 */
export function SearchInput({
  value,
  onChange,
  placeholder,
  label = "Search",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label?: string;
}) {
  const id = useId();
  const [draft, setDraft] = useState(value);
  // When the value changes from outside (e.g. "Clear filters", Back button),
  // show it: React's "adjust state while rendering" pattern, no extra effect.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setDraft(value);
  }
  useEffect(() => {
    if (draft === value) return;
    const timer = setTimeout(() => onChange(draft), 300);
    return () => clearTimeout(timer);
  }, [draft, value, onChange]);

  return (
    <div className="relative min-w-0 flex-[1_1_300px]">
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <SearchIcon
        className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted"
        aria-hidden="true"
      />
      <Input
        id={id}
        type="search"
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        className="pl-10"
      />
    </div>
  );
}

export type Option = { value: string; label: string };

/** A labelled dropdown filter. Empty value = "all". */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  allLabel: string;
}) {
  const id = useId();
  return (
    <div className="min-w-[150px] flex-[0_1_200px]">
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <NativeSelect id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </NativeSelect>
    </div>
  );
}

/** "Standard 10 ×" chips for the active filters, plus "Clear filters". */
export function ActiveFilters({
  items,
  onClearAll,
}: {
  items: { key: string; label: string; onRemove: () => void }[];
  onClearAll: () => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={item.onRemove}
          className="inline-flex min-h-8 items-center gap-1 rounded-full bg-primary-tint px-3 text-xs font-bold text-primary"
          aria-label={`Remove filter ${item.label}`}
        >
          {item.label}
          <XIcon className="size-3.5" aria-hidden="true" />
        </button>
      ))}
      <button type="button" onClick={onClearAll} className="text-[13px] font-bold text-primary">
        Clear filters
      </button>
    </div>
  );
}
