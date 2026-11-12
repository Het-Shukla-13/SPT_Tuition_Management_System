import { parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";

import { PageHeader } from "@/components/shared/PageHeader";
import { cn } from "@/lib/utils";

import { AccountsTab } from "../components/AccountsTab";
import { PaymentsTab } from "../components/PaymentsTab";
import { RolloverTab } from "../components/RolloverTab";
import { StructuresTab } from "../components/StructuresTab";

const TABS = [
  { key: "accounts", title: "Accounts", Component: AccountsTab },
  { key: "payments", title: "Payments", Component: PaymentsTab },
  { key: "structures", title: "Fee structures", Component: StructuresTab },
  { key: "rollover", title: "Year-end rollover", Component: RolloverTab },
] as const;
type TabKey = (typeof TABS)[number]["key"];

// Every URL parameter a tab uses, so switching tabs clears the others.
const PARAMS = {
  tab: parseAsStringLiteral(TABS.map((t) => t.key) as [TabKey, ...TabKey[]]).withDefault(
    "accounts",
  ),
  page: parseAsString,
  search: parseAsString,
  academic_year: parseAsString,
  academic_year__board: parseAsString,
  student__standard: parseAsString,
  ordering: parseAsString,
  method: parseAsString,
  entry_date__gte: parseAsString,
  entry_date__lte: parseAsString,
  standard: parseAsString,
};
const CLEARED = Object.fromEntries(
  Object.keys(PARAMS)
    .filter((k) => k !== "tab")
    .map((k) => [k, null]),
);

export function FeesPage() {
  const [{ tab }, setParams] = useQueryStates(PARAMS);
  const current = TABS.find((t) => t.key === tab) ?? TABS[0];

  return (
    <>
      <PageHeader
        title="Fees"
        eyebrow="Each board has its own academic year. Fees are recorded here; parents pay at the institute."
      />
      <nav
        aria-label="Fee sections"
        className="-mb-2 flex gap-1 overflow-x-auto border-b border-line"
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-current={t.key === current.key ? "page" : undefined}
            onClick={() => void setParams({ tab: t.key, ...CLEARED }, { history: "push" })}
            className={cn(
              "h-11 shrink-0 border-b-[3px] px-3 text-[15px] whitespace-nowrap",
              t.key === current.key
                ? "border-primary font-extrabold text-primary"
                : "border-transparent font-semibold text-muted hover:text-ink",
            )}
          >
            {t.title}
          </button>
        ))}
      </nav>
      <current.Component key={current.key} />
    </>
  );
}
