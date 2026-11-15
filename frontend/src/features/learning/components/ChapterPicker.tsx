import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { useReferenceOptions } from "@/features/academics";

/**
 * Chapters of the chosen standard + subject, from the chosen boards (every
 * board's when none are chosen). With several boards, each says its board.
 */
export function ChapterPicker({
  boards,
  standard,
  subject,
  value,
  onChange,
  error,
}: {
  boards: number[];
  standard: string;
  subject: string;
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
}) {
  const ready = Boolean(standard && subject);
  const chapters = useReferenceOptions(
    "chapters",
    { standard, subject, ordering: "number" },
    ready,
  );

  if (!ready) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">Choose the standard and subject first.</span>
      </div>
    );
  }
  const shown = (chapters.data ?? []).filter(
    (c) => boards.length === 0 || boards.includes(Number(c.board)),
  );
  if (chapters.data && shown.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">
          No chapters set up for this class yet (Academics setup → Chapters). You can still upload.
        </span>
      </div>
    );
  }
  const labelBoard = boards.length !== 1;
  return (
    <ChipToggleGroup
      label="Chapters"
      options={shown.map((c) => ({
        value: c.id,
        label: `${labelBoard ? `${String(c.board_code)} · ` : ""}${String(c.number)}. ${String(c.name)}`,
      }))}
      value={value.filter((id) => shown.some((c) => c.id === id))}
      onChange={onChange}
      loading={chapters.isPending}
      error={error}
    />
  );
}
