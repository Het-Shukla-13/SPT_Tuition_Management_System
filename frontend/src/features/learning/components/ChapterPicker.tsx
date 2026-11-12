import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { useReferenceOptions } from "@/features/academics";

/** Chapters of the chosen board + standard + subject, as chips. */
export function ChapterPicker({
  board,
  standard,
  subject,
  value,
  onChange,
  error,
}: {
  board: string;
  standard: string;
  subject: string;
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
}) {
  const ready = Boolean(board && standard && subject);
  const chapters = useReferenceOptions(
    "chapters",
    { board, standard, subject, ordering: "number" },
    ready,
  );

  if (!ready) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">Choose the board, standard and subject first.</span>
      </div>
    );
  }
  if (chapters.data && chapters.data.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">
          No chapters set up for this class yet (Academics setup → Chapters). You can still upload.
        </span>
      </div>
    );
  }
  return (
    <ChipToggleGroup
      label="Chapters"
      options={(chapters.data ?? []).map((c) => ({
        value: c.id,
        label: `${String(c.number)}. ${String(c.name)}`,
      }))}
      value={value}
      onChange={onChange}
      loading={chapters.isPending}
      error={error}
    />
  );
}
