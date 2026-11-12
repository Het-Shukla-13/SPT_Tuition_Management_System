import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "brand";

const toneClass: Record<Tone, string> = {
  success: "bg-success-bg text-success",
  warning: "bg-warning-bg text-warning",
  danger: "bg-danger-bg text-danger",
  info: "bg-info-bg text-info",
  neutral: "bg-neutral-bg text-neutral",
  brand: "bg-primary-tint text-primary",
};

/**
 * ONE mapping from an API status to how it looks, used everywhere, so
 * "ACTIVE" is the same green on every screen.
 */
const STATUS: Record<string, { label: string; tone: Tone }> = {
  // students
  ACTIVE: { label: "Active", tone: "success" },
  LEFT: { label: "Left", tone: "neutral" },
  COMPLETED: { label: "Completed", tone: "info" },
  ON_HOLD: { label: "On hold", tone: "warning" },
  // fees
  PAID: { label: "Paid", tone: "success" },
  DUE: { label: "Due", tone: "warning" },
  OVERDUE: { label: "Overdue", tone: "danger" },
  REVERSED: { label: "Reversed", tone: "neutral" },
  PENDING: { label: "Pending", tone: "warning" },
  // enquiries
  CONTACTED: { label: "Contacted", tone: "info" },
  ACCEPTED: { label: "Admitted", tone: "success" },
  REJECTED: { label: "Not proceeding", tone: "neutral" },
  PARTIAL: { label: "Part paid", tone: "warning" },
  CREDIT: { label: "Advance credit", tone: "info" },
  CARRIED_FORWARD: { label: "Carried forward", tone: "neutral" },
  // tests
  UPCOMING: { label: "Upcoming", tone: "info" },
  ABSENT: { label: "Absent", tone: "danger" },
  LOCKED: { label: "Locked", tone: "neutral" },
  // users & enquiries
  INVITED: { label: "Invited", tone: "info" },
  INACTIVE: { label: "Deactivated", tone: "neutral" },
  NEW: { label: "New", tone: "brand" },
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold whitespace-nowrap",
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** <StatusBadge status="ACTIVE" /> → green "Active". Unknown statuses show as-is, neutral. */
export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const entry = STATUS[status] ?? { label: status, tone: "neutral" as const };
  return (
    <Badge tone={entry.tone} className={className}>
      {entry.label}
    </Badge>
  );
}
