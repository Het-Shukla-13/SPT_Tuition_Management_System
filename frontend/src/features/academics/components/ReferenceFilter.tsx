import { FilterSelect } from "@/components/shared/FilterBar";

import { type ReferenceItem, type ReferenceKey, useReferenceOptions } from "../api";

const DEFAULT_LABELS: Partial<Record<ReferenceKey, (i: ReferenceItem) => string>> = {
  boards: (i) => String(i.code),
  schools: (i) => `${String(i.name)}, ${String(i.city)}`,
  "academic-years": (i) => `${String(i.board_code)} ${String(i.name)}`,
};

/** A list filter whose options are a reference type (boards, standards...). Reused on every list. */
export function ReferenceFilter({
  resource,
  label,
  allLabel,
  value,
  onChange,
  optionLabel,
}: {
  resource: ReferenceKey;
  label: string;
  allLabel: string;
  value: string;
  onChange: (value: string) => void;
  optionLabel?: (item: ReferenceItem) => string;
}) {
  const options = useReferenceOptions(resource);
  const toLabel =
    optionLabel ?? DEFAULT_LABELS[resource] ?? ((i: ReferenceItem) => String(i.name ?? i.id));
  return (
    <FilterSelect
      label={label}
      allLabel={allLabel}
      value={value}
      onChange={onChange}
      options={(options.data ?? []).map((o) => ({ value: String(o.id), label: toLabel(o) }))}
    />
  );
}
