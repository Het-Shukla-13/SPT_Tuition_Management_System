import { cn } from "@/lib/utils";

/** The Chalkboard mark: a small board with chalk. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-[9px] border border-board-line bg-primary",
        className,
      )}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 24 24"
        className="size-[60%]"
        fill="none"
        stroke="var(--color-chalk)"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <rect x="3" y="4" width="18" height="12" rx="1.5" />
        <path d="M7 20l2-4M17 20l-2-4M8 10h5" />
      </svg>
    </span>
  );
}

export const INSTITUTE_NAME = "Sai Personal Tuitions";

export function Logo({ subtitle = true }: { subtitle?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="flex flex-col leading-tight">
        <span className="text-[17px] font-extrabold text-white">Chalkboard</span>
        {subtitle && <span className="text-xs text-board-muted">{INSTITUTE_NAME}</span>}
      </span>
    </span>
  );
}
