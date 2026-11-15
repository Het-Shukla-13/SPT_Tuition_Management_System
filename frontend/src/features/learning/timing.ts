/** Test timing as the forms hold it (strings), and what the server expects. */

export type Timing = { date: string; time: string; duration: string };

/** What the server expects: a date, an optional time, and minutes. */
export const timingBody = (t: Timing) => ({
  test_date: t.date || null,
  test_time: t.date && t.time ? t.time : null,
  duration_minutes: t.duration ? Number(t.duration) : null,
});

/** Explains, in words, when students can open the paper with these settings. */
export function timingSummary(t: Timing) {
  if (!t.date) return "Students can open the paper straight away.";
  if (!t.time) return "The paper and answer key open at 8:00 AM on that date.";
  return "The paper opens at the start time; the answer key and marks after the duration.";
}

/** A stored start back into the form's date + time (local), e.g. for Edit time. */
export function timingFrom(
  startsAt: string | null | undefined,
  hasTime: boolean,
  duration: string,
): Timing {
  if (!startsAt) return { date: "", time: "", duration };
  const d = new Date(startsAt);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: hasTime ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : "",
    duration,
  };
}
