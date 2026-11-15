/**
 * Academic years belong to one board each, and boards often share a year name
 * (CBSE "2026-27", GSEB "2026-27"). Helpers to pick years sensibly.
 */
import type { ReferenceItem } from "@/features/academics";

export type Year = {
  id: number;
  board: number;
  name: string;
  start_date: string;
  is_current: boolean;
};

export const asYears = (items: ReferenceItem[] | undefined): Year[] =>
  (items ?? []).map((i) => ({
    id: i.id,
    board: Number(i.board),
    name: String(i.name),
    start_date: String(i.start_date ?? ""),
    is_current: Boolean(i.is_current),
  }));

/** Each year name once, newest first; only that board's when a board is chosen. */
export function yearNameOptions(years: Year[], board?: string) {
  const names = new Set(
    years.filter((y) => !board || String(y.board) === board).map((y) => y.name),
  );
  return [...names]
    .sort((a, b) => b.localeCompare(a))
    .map((name) => ({ value: name, label: name }));
}

/** One board's years, newest first. */
export const yearsOfBoard = (years: Year[], board: string) =>
  years
    .filter((y) => String(y.board) === board)
    .sort((a, b) => b.start_date.localeCompare(a.start_date));

/** The board's years that start after its current one: the only sensible rollover targets. */
export function laterYears(years: Year[], board: string) {
  const own = yearsOfBoard(years, board);
  const current = own.find((y) => y.is_current);
  return own
    .filter((y) => !current || y.start_date > current.start_date)
    .sort((a, b) => a.start_date.localeCompare(b.start_date));
}
