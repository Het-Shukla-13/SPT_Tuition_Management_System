/** Guardians: contacts on file for a student (not logins). The first is the main contact. */

export type GuardianRow = { name: string; relation: string; phone: string; email: string };

export const MAX_GUARDIANS = 4;
export const emptyGuardian = (): GuardianRow => ({ name: "", relation: "", phone: "", email: "" });

const isBlank = (g: GuardianRow) =>
  !g.name.trim() && !g.relation.trim() && !g.phone.trim() && !g.email.trim();

/** Rows the user left completely empty are dropped; the rest are trimmed. */
export function cleanGuardians(rows: GuardianRow[]): GuardianRow[] {
  return rows
    .filter((g) => !isBlank(g))
    .map((g) => ({
      name: g.name.trim(),
      relation: g.relation.trim(),
      phone: g.phone.trim(),
      email: g.email.trim(),
    }));
}

/** Errors keyed "index.field" (e.g. "1.name"), checked before calling the server. */
export function validateGuardians(rows: GuardianRow[]): Record<string, string> {
  const errors: Record<string, string> = {};
  rows.forEach((g, i) => {
    if (isBlank(g)) return;
    if (!g.name.trim()) errors[`${i}.name`] = "Enter the guardian's name.";
    if (g.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(g.email.trim()))
      errors[`${i}.email`] = "Enter a valid email address.";
    if (g.phone.trim() && !/^\+?[\d\s-]{10,16}$/.test(g.phone.trim()))
      errors[`${i}.phone`] = "Enter a 10-digit mobile number.";
  });
  return errors;
}

/**
 * The server answers guardian problems as errors.guardians = [{phone: [...]}, {}].
 * Map them onto "index.field" keys. `kept` maps cleaned rows back to form rows.
 */
export function guardianServerErrors(errors: unknown, kept: number[]): Record<string, string> {
  const list = (errors as { guardians?: unknown } | null)?.guardians;
  if (!Array.isArray(list)) return {};
  const out: Record<string, string> = {};
  list.forEach((rowErrors, i) => {
    for (const [field, messages] of Object.entries((rowErrors ?? {}) as Record<string, string[]>)) {
      out[`${kept[i] ?? i}.${field}`] = [messages].flat().join(" ");
    }
  });
  return out;
}

/** Positions of the non-empty rows, so server errors land on the right row. */
export const keptIndexes = (rows: GuardianRow[]) => rows.flatMap((g, i) => (isBlank(g) ? [] : [i]));
