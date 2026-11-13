export type ExtraChoice = { on: boolean; amount: string };
type AddOn = { subject: number; subject_name: string; amount: string };

/** The extra fee for each optional subject chosen (e.g. Gujarati), from the fee structure. */
export function optionalSubjectRows(
  addOns: AddOn[],
  subjects: number[],
  choices: Record<number, ExtraChoice>,
) {
  return addOns
    .filter((a) => subjects.includes(a.subject))
    .map((a) => ({
      ...a,
      choice: choices[a.subject] ?? { on: true, amount: String(Number(a.amount)) },
    }));
}
