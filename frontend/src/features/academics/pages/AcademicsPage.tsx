import { parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";

import { PageHeader } from "@/components/shared/PageHeader";
import { cn } from "@/lib/utils";

import type { ReferenceKey } from "../api";
import { ReferenceSection } from "../components/ReferenceSection";
import { REFERENCE_CONFIGS } from "../config";

const KEYS = REFERENCE_CONFIGS.map((c) => c.key) as [ReferenceKey, ...ReferenceKey[]];

// Every URL parameter any tab uses, so switching tabs can clear them at once.
const PARAMS = {
  tab: parseAsStringLiteral(KEYS).withDefault("academic-years"),
  page: parseAsString,
  search: parseAsString,
  is_active: parseAsString,
  board: parseAsString,
  standard: parseAsString,
  subject: parseAsString,
};
const CLEARED = {
  page: null,
  search: null,
  is_active: null,
  board: null,
  standard: null,
  subject: null,
};

/** Academics setup: one tab per reference type, the tab kept in the URL. */
export function AcademicsPage() {
  const [{ tab }, setParams] = useQueryStates(PARAMS);
  const config = REFERENCE_CONFIGS.find((c) => c.key === tab) ?? REFERENCE_CONFIGS[0]!;

  return (
    <>
      <PageHeader
        title="Academics setup"
        eyebrow="Years, boards, standards, subjects, schools and chapters"
      />
      <nav
        aria-label="Academics sections"
        className="-mb-2 flex gap-1 overflow-x-auto border-b border-line"
      >
        {REFERENCE_CONFIGS.map((c) => (
          <button
            key={c.key}
            type="button"
            aria-current={c.key === config.key ? "page" : undefined}
            onClick={() => void setParams({ tab: c.key, ...CLEARED }, { history: "push" })}
            className={cn(
              "h-11 shrink-0 border-b-[3px] px-3 text-[15px] whitespace-nowrap",
              c.key === config.key
                ? "border-primary font-extrabold text-primary"
                : "border-transparent font-semibold text-muted hover:text-ink",
            )}
          >
            {c.title}
          </button>
        ))}
      </nav>
      <ReferenceSection key={config.key} config={config} />
    </>
  );
}
