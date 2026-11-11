import { useCallback, useEffect, useState } from "react";

/**
 * Seconds left until something is allowed again ("Resend code in 0:42",
 * "Try again in 14:59"). `start(seconds)` (re)starts it.
 */
export function useCountdown(initialSeconds = 0) {
  const [endsAt, setEndsAt] = useState(() =>
    initialSeconds > 0 ? Date.now() + initialSeconds * 1000 : 0,
  );
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (endsAt <= Date.now()) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [endsAt]);

  const start = useCallback((seconds: number) => {
    setNow(Date.now());
    setEndsAt(Date.now() + seconds * 1000);
  }, []);

  const remaining = Math.max(0, Math.ceil((endsAt - now) / 1000));
  return { remaining, start, label: formatClock(remaining) };
}

/** 125 → "2:05" */
export function formatClock(seconds: number) {
  const m = Math.floor(seconds / 60);
  return `${m}:${String(seconds % 60).padStart(2, "0")}`;
}
