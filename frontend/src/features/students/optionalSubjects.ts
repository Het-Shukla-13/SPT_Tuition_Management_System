export type ExtraChoice = { on: boolean; amount: string };
type AddOn = { subject: number; subject_name: string; amount: string };

/**
 * A subject moved for this student only (the fee structure never changes):
 * - "optional": an included subject charged as its own line; `amount` came off the standard fee.
 * - "included": a structure-optional subject now covered by the standard fee; `amount` went into it.
 */
export type SubjectMove = { to: "optional" | "included"; amount: string };

export type OptionalRow = AddOn & {
  choice: ExtraChoice;
  /** Made optional for this student (no structure amount; can be made included again). */
  moved: boolean;
};

/**
 * The extra fee for each optional subject chosen (e.g. Gujarati), from the fee
 * structure, plus any subject staff made optional for this student.
 */
export function optionalSubjectRows(
  addOns: AddOn[],
  subjects: number[],
  choices: Record<number, ExtraChoice>,
  moves: Record<number, SubjectMove> = {},
  names: Record<number, string> = {},
): OptionalRow[] {
  const fromStructure = addOns
    .filter((a) => subjects.includes(a.subject) && moves[a.subject]?.to !== "included")
    .map((a) => ({
      ...a,
      choice: choices[a.subject] ?? { on: true, amount: String(Number(a.amount)) },
      moved: false,
    }));
  const madeOptional = subjects
    .filter((id) => moves[id]?.to === "optional")
    .map((id) => ({
      subject: id,
      subject_name: names[id] ?? "",
      amount: "",
      choice: { on: true, amount: moves[id]?.amount ?? "" },
      moved: true,
    }));
  return [...fromStructure, ...madeOptional];
}
