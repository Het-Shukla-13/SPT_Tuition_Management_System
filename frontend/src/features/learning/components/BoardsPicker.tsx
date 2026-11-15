import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { useReferenceOptions } from "@/features/academics";

/** Which boards a test or note suits. None chosen = every board. */
export function BoardsPicker({
  value,
  onChange,
  error,
}: {
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
}) {
  const boards = useReferenceOptions("boards");
  return (
    <div className="flex flex-col gap-1">
      <ChipToggleGroup
        label="Boards (optional)"
        options={(boards.data ?? []).map((b) => ({ value: b.id, label: String(b.code) }))}
        value={value}
        onChange={onChange}
        loading={boards.isPending}
        error={error}
      />
      <span className="text-xs text-muted">
        {value.length === 0
          ? "None chosen: suits every board."
          : "Only students of these boards will see it in the assign list by default."}
      </span>
    </div>
  );
}
