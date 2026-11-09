import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** A number with a label, for dashboards (staff and portal). */
export function StatCard({
  label,
  value,
  hint,
  tone,
  loading,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "warning" | "success";
  loading?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5 rounded-[var(--radius-card)] border border-line bg-surface px-5 py-4">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      {loading ? (
        <Skeleton className="h-8 w-28" />
      ) : (
        <span
          className={cn(
            "tabular text-[28px] font-extrabold tracking-tight",
            tone === "warning" && "text-warning",
            tone === "success" && "text-success",
          )}
        >
          {value}
        </span>
      )}
      {hint && <span className="text-[13px] text-muted">{hint}</span>}
    </div>
  );
}
