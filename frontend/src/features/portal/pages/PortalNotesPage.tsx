import { FileTextIcon } from "lucide-react";
import { parseAsString, useQueryStates } from "nuqs";
import { toast } from "sonner";

import { FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/envelope";
import { formatDate } from "@/lib/format";

import { filterNotes, openNote, usePortalNotes } from "../api";
import { PortalHeader } from "../components/PortalHeader";
import { useActiveStudent } from "../student";

const PARAMS = { search: parseAsString.withDefault(""), subject: parseAsString.withDefault("") };

export function PortalNotesPage() {
  const { student } = useActiveStudent();
  const notes = usePortalNotes(student.id);
  const [{ search, subject }, setParams] = useQueryStates(PARAMS);

  const all = notes.data ?? [];
  const subjects = [...new Map(all.map((n) => [String(n.subject_id), n.subject])).entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  const shown = filterNotes(all, search, subject);

  return (
    <div className="flex flex-col gap-4 p-4">
      <PortalHeader title="Notes" />
      <div className="flex flex-col gap-2">
        <SearchInput
          value={search}
          onChange={(v) => void setParams({ search: v || null })}
          placeholder="Search title, subject or chapter"
        />
        {subjects.length > 1 && (
          <FilterSelect
            label="Subject"
            allLabel="All subjects"
            value={subject}
            onChange={(v) => void setParams({ subject: v || null })}
            options={subjects}
          />
        )}
      </div>
      {notes.isPending ? (
        <>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </>
      ) : notes.error ? (
        <ErrorState error={notes.error} onRetry={() => void notes.refetch()} />
      ) : shown.length === 0 ? (
        <EmptyState
          title={all.length ? "No notes match" : "No notes shared yet"}
          description={
            all.length
              ? "Try another word or subject."
              : "Notes from the teachers will appear here."
          }
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {shown.map((n) => (
            <li
              key={n.id}
              className="flex flex-col gap-2 rounded-[var(--radius-card)] border border-line bg-surface p-4"
            >
              <span className="text-xs font-bold tracking-wide text-muted uppercase">
                {n.subject}
              </span>
              <b className="text-base">{n.title}</b>
              {n.chapters.length > 0 && (
                <span className="text-sm text-muted">{n.chapters.join(" · ")}</span>
              )}
              {(n.remarks || n.description) && (
                <p className="text-sm">{n.remarks || n.description}</p>
              )}
              <span className="flex items-center justify-between gap-2">
                <span className="text-xs text-muted">Shared {formatDate(n.assigned_at)}</span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    void openNote(student.id, n.id).catch((e: unknown) =>
                      toast.error(e instanceof ApiError ? e.message : "Couldn't open the notes."),
                    )
                  }
                >
                  <FileTextIcon className="size-4" aria-hidden="true" />
                  Open
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
