import type { ComponentProps } from "react";

import { NativeSelect } from "@/components/ui/input";

import { type ReferenceItem, type ReferenceKey, useReferenceOptions } from "../api";

const LABELS: Partial<Record<ReferenceKey, (i: ReferenceItem) => string>> = {
  boards: (i) => `${String(i.code)} · ${String(i.name)}`,
  // Each board has its own year, often with the same name: always say which board.
  "academic-years": (i) => `${String(i.board_code)} ${String(i.name)}`,
  schools: (i) => `${String(i.name)}, ${String(i.city)}`,
  chapters: (i) => `${String(i.number)}. ${String(i.name)}`,
};

/**
 * A form dropdown of active reference items (board, standard, school...).
 * Spread react-hook-form's register() or FormField's props onto it.
 */
export function ReferenceSelect({
  resource,
  filters,
  placeholder = "Choose…",
  ...props
}: Omit<ComponentProps<"select">, "children"> & {
  resource: ReferenceKey;
  filters?: Record<string, string | number>;
  placeholder?: string;
}) {
  const options = useReferenceOptions(resource, filters);
  const toLabel = LABELS[resource] ?? ((i: ReferenceItem) => String(i.name ?? i.id));
  return (
    <NativeSelect {...props} disabled={props.disabled || options.isPending}>
      <option value="">{options.isPending ? "Loading…" : placeholder}</option>
      {options.data?.map((o) => (
        <option key={o.id} value={o.id}>
          {toLabel(o)}
        </option>
      ))}
    </NativeSelect>
  );
}
