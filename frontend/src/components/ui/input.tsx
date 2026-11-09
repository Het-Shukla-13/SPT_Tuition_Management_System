import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const fieldBase =
  "w-full rounded-[var(--radius-control)] border border-line-strong bg-surface px-3.5 text-[15px] font-medium text-ink placeholder:text-muted/80 disabled:cursor-not-allowed disabled:bg-subtle aria-invalid:border-2 aria-invalid:border-danger";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input data-slot="input" className={cn(fieldBase, "h-11", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldBase, "min-h-24 py-2.5", className)}
      {...props}
    />
  );
}

/**
 * A native <select>: on phones it opens the system picker, which is faster and
 * more familiar for parents than a custom dropdown.
 */
export function NativeSelect({ className, children, ...props }: ComponentProps<"select">) {
  return (
    <select
      data-slot="select"
      className={cn(
        fieldBase,
        "h-11 appearance-none bg-no-repeat pr-9",
        "select-chevron",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label data-slot="label" className={cn("text-[13px] font-bold", className)} {...props} />;
}
