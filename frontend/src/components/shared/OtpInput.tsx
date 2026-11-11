import { type ClipboardEvent, type KeyboardEvent, useRef } from "react";

import { cn } from "@/lib/utils";

const LENGTH = 6;

/**
 * Six boxes for a one-time code. Typing moves to the next box, Backspace goes
 * back, pasting "123456" (or "123 456") fills all of them, and phones offer
 * the code from the SMS/email automatically (autocomplete="one-time-code").
 */
export function OtpInput({
  value,
  onChange,
  invalid,
  disabled,
  autoFocus,
  label = "6-digit code",
}: {
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  disabled?: boolean;
  autoFocus?: boolean;
  label?: string;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length: LENGTH }, (_, i) => value[i] ?? "");

  const focus = (index: number) => refs.current[Math.max(0, Math.min(LENGTH - 1, index))]?.focus();

  const setAt = (index: number, raw: string) => {
    const incoming = raw.replace(/\D/g, "");
    if (!incoming) return;
    // One box can receive several digits (autofill / fast typing): spread them.
    const next = [...digits];
    for (let i = 0; i < incoming.length && index + i < LENGTH; i++) next[index + i] = incoming[i]!;
    onChange(next.join("").slice(0, LENGTH));
    focus(index + incoming.length);
  };

  const onKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Backspace") {
      event.preventDefault();
      const next = [...digits];
      if (next[index]) {
        next[index] = "";
      } else if (index > 0) {
        next[index - 1] = "";
        focus(index - 1);
      }
      onChange(next.join(""));
    } else if (event.key === "ArrowLeft") {
      focus(index - 1);
    } else if (event.key === "ArrowRight") {
      focus(index + 1);
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (pasted) {
      onChange(pasted);
      focus(pasted.length);
    }
  };

  return (
    <div role="group" aria-label={label} className="flex justify-between gap-2">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          value={digit}
          onChange={(e) => setAt(index, e.target.value)}
          onKeyDown={(e) => onKeyDown(index, e)}
          onPaste={onPaste}
          onFocus={(e) => e.target.select()}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          maxLength={LENGTH}
          disabled={disabled}
          autoFocus={autoFocus && index === 0}
          aria-label={`Digit ${index + 1}`}
          aria-invalid={invalid || undefined}
          className={cn(
            "tabular h-14 w-full max-w-[52px] rounded-xl border bg-surface text-center text-2xl font-extrabold",
            invalid
              ? "border-2 border-danger"
              : "border-line-strong focus:border-2 focus:border-primary",
          )}
        />
      ))}
    </div>
  );
}
