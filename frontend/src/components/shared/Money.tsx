import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * A rupee amount from the API ("26000.00" → ₹26,000), with tabular digits so
 * columns line up. `tone="due"` colours pending amounts.
 */
export function Money({
  value,
  tone,
  className,
}: {
  value: string | number | null | undefined;
  tone?: "due" | "paid";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "tabular",
        tone === "due" && "font-extrabold text-warning",
        tone === "paid" && "text-success",
        className,
      )}
    >
      {formatMoney(value)}
    </span>
  );
}
