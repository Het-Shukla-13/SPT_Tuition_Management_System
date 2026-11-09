import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Grey placeholder shown while data loads (instead of a spinner). */
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-line/70", className)}
      {...props}
    />
  );
}
