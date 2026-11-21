/** Rupee amounts typed into fee forms: "20000" or "20000.50". */
export const AMOUNT = /^\d+(\.\d{1,2})?$/;

export const isAmount = (value: string) => AMOUNT.test(value.trim());

/** A typed amount as a number; anything not (yet) an amount counts as 0. */
export const toAmount = (value: string) => (isAmount(value) ? Number(value.trim()) : 0);

/**
 * Move money in or out of a typed fee, e.g. when a subject becomes optional
 * and its amount is charged separately. A fee that isn't a number is left alone.
 */
export function shiftFee(fee: string, delta: number): string {
  const trimmed = fee.trim();
  if (delta === 0 || !/^-?\d+(\.\d{1,2})?$/.test(trimmed)) return fee;
  return String(Math.round((Number(trimmed) + delta) * 100) / 100);
}
