import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { useReferenceOptions } from "@/features/academics";

/** Topics (chapters) of the chosen standard + subject, A to Z, as chips. Any board. */
export function ChapterPicker({
  standard,
  subject,
  value,
  onChange,
  error,
}: {
  standard: string;
  subject: string;
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
}) {
  const ready = Boolean(standard && subject);
  const chapters = useReferenceOptions("chapters", { standard, subject, ordering: "name" }, ready);

  if (!ready) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">Choose the standard and subject first.</span>
      </div>
    );
  }
  if (chapters.data && chapters.data.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-bold">Chapters</span>
        <span className="text-sm text-muted">
          No chapters set up for this standard and subject yet (Academics setup → Chapters). You can
          still upload.
        </span>
      </div>
    );
  }
  return (
    <ChipToggleGroup
      label="Chapters"
      options={(chapters.data ?? []).map((c) => ({ value: c.id, label: String(c.name) }))}
      value={value}
      onChange={onChange}
      loading={chapters.isPending}
      error={error}
    />
  );
}
