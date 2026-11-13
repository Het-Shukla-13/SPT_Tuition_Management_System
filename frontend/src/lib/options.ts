/** Choices used by more than one feature. Values match the backend's enums. */

export const MEDIUM_OPTIONS = [
  { value: "ENGLISH", label: "English" },
  { value: "GUJARATI", label: "Gujarati" },
  { value: "HINDI", label: "Hindi" },
];

export const mediumLabel = (value: string | null | undefined) =>
  MEDIUM_OPTIONS.find((m) => m.value === value)?.label ?? "";
