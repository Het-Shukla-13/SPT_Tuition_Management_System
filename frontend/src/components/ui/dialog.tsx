import { XIcon } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

/**
 * Accessible modal (focus trap, Esc to close, screen-reader title).
 * `side="right"` turns it into a drawer (e.g. the staff menu on phones).
 */
export function DialogContent({
  title,
  description,
  side = "center",
  className,
  children,
  ...props
}: ComponentProps<typeof DialogPrimitive.Content> & {
  title: string;
  description?: ReactNode;
  side?: "center" | "left";
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/40" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-50 flex flex-col gap-4 bg-surface p-6 shadow-xl focus:outline-none",
          side === "center" &&
            "top-1/2 left-1/2 max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[var(--radius-card)]",
          side === "left" && "inset-y-0 left-0 w-[280px] max-w-[85vw] p-0",
          className,
        )}
        {...props}
      >
        <div className={cn("flex items-start justify-between gap-4", side === "left" && "sr-only")}>
          <div className="flex flex-col gap-1">
            <DialogPrimitive.Title className="text-xl font-extrabold">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-sm text-muted">
                {description}
              </DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close
            aria-label="Close"
            className="-m-2 flex size-11 items-center justify-center rounded-full text-muted hover:bg-subtle"
          >
            <XIcon className="size-5" />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
