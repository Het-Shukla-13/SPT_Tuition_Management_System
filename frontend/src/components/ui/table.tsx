import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Plain table pieces with Chalkboard styling. DataTable builds on these. */
export function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface">
      <table className={cn("w-full border-collapse", className)} {...props} />
    </div>
  );
}

export function Th({ className, ...props }: ComponentProps<"th">) {
  return (
    <th
      className={cn(
        "border-b border-line bg-subtle px-4 py-3 text-left text-xs font-bold tracking-wider whitespace-nowrap text-muted uppercase",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: ComponentProps<"td">) {
  return (
    <td
      className={cn("border-b border-line/60 px-4 py-3 text-sm whitespace-nowrap", className)}
      {...props}
    />
  );
}

export function Tr({ className, ...props }: ComponentProps<"tr">) {
  return <tr className={cn("hover:bg-subtle", className)} {...props} />;
}
