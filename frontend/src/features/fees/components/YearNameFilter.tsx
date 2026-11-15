import { FilterSelect } from "@/components/shared/FilterBar";
import { useReferenceOptions } from "@/features/academics";

import { asYears, yearNameOptions } from "../years";

/**
 * Pick a year by name ("2026-27"), on its own or with a board. With no board,
 * it means every board's year of that name.
 */
export function YearNameFilter({
  value,
  onChange,
  board,
}: {
  value: string;
  onChange: (value: string) => void;
  board?: string;
}) {
  const years = useReferenceOptions("academic-years");
  return (
    <FilterSelect
      label="Academic year"
      allLabel="All years"
      value={value}
      onChange={onChange}
      options={yearNameOptions(asYears(years.data), board)}
    />
  );
}
