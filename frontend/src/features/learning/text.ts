import type { Kind } from "./api";

/** Wording that differs between tests and notes. */
export const KIND_TEXT: Record<Kind, { title: string; singular: string; intro: string }> = {
  tests: {
    title: "Tests",
    singular: "test",
    intro:
      "Tests are written on paper in class. Upload the paper (and answer key), assign it, then enter marks.",
  },
  notes: {
    title: "Notes",
    singular: "notes",
    intro:
      "Chapter notes as PDFs. Upload once, assign to students; they always get the newest version.",
  },
};
