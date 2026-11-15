import { useReferenceOptions } from "./api";

/**
 * Academic year names across all boards ("2026-27" once, newest first), and the
 * current one (the newest current year of any board) as a sensible default.
 */
export function useYearNames() {
  const years = useReferenceOptions("academic-years");
  const items = years.data ?? [];
  const names = [...new Set(items.map((y) => String(y.name)))].sort((a, b) => b.localeCompare(a));
  const current = items
    .filter((y) => Boolean(y.is_current))
    .sort((a, b) => String(b.start_date).localeCompare(String(a.start_date)))[0];
  return {
    names,
    current: current ? String(current.name) : undefined,
    isPending: years.isPending,
  };
}
