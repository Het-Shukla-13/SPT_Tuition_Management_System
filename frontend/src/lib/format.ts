/**
 * Display formatting. The API sends money as exact strings ("26000.00"):
 * we only ever FORMAT them, never do floating-point arithmetic on them.
 */
import { format, formatDistanceToNowStrict, isToday, isYesterday, parseISO } from "date-fns";

const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** "26000.00" → "₹26,000"; "1234.5" → "₹1,234.5"; null → "–". */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "–";
  return rupees.format(amount);
}

/** Marks: "21.50" → "21.5", "25.00" → "25". */
export function formatMarks(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const n = Number(value);
  return Number.isFinite(n) ? String(Number(n.toFixed(2))) : "–";
}

function toDate(value: string | Date): Date {
  return typeof value === "string" ? parseISO(value) : value;
}

/** "9 Nov 2026" */
export function formatDate(value: string | Date | null | undefined): string {
  return value ? format(toDate(value), "d MMM yyyy") : "–";
}

/** "9 Nov 2026, 4:00 pm" */
export function formatDateTime(value: string | Date | null | undefined): string {
  return value ? format(toDate(value), "d MMM yyyy, h:mm aaa") : "–";
}

/** "Today 10:12 am" / "Yesterday" / "6 Nov" for activity lists. */
export function formatRelativeDay(value: string | Date | null | undefined): string {
  if (!value) return "–";
  const date = toDate(value);
  if (isToday(date)) return `Today ${format(date, "h:mm aaa")}`;
  if (isYesterday(date)) return "Yesterday";
  return format(date, "d MMM");
}

/** "3 days ago" */
export function formatAgo(value: string | Date | null | undefined): string {
  return value ? `${formatDistanceToNowStrict(toDate(value))} ago` : "–";
}

/** "Kavita Shah" → "KS"; "" → "?" */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts;
  return letters.map((p) => p?.[0]?.toUpperCase() ?? "").join("") || "?";
}

/** "+919876543210" → "+91 98765 43210" */
export function formatPhone(value: string | null | undefined): string {
  if (!value) return "–";
  const match = /^\+91(\d{5})(\d{5})$/.exec(value);
  return match ? `+91 ${match[1]} ${match[2]}` : value;
}
