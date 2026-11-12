import { useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/envelope";
import { formatDate, formatMarks } from "@/lib/format";

import {
  isTest,
  type Kind,
  type LearningItem,
  useArchiveItem,
  useAssignments,
  useItem,
  useUpdateItem,
} from "../api";
import { AssignDialog } from "../components/AssignDialog";
import { AssignmentsCard } from "../components/AssignmentsCard";
import { FilesCard } from "../components/FilesCard";
import { KIND_TEXT } from "../text";

export function LearningDetailPage({ kind }: { kind: Kind }) {
  const id = Number(useParams().id);
  const item = useItem(kind, id);
  const assignments = useAssignments(kind, id);
  const [params, setParams] = useSearchParams();
  const assigning = params.get("assign") === "1";
  const setAssigning = (open: boolean) => setParams(open ? { assign: "1" } : {}, { replace: true });
  const [editing, setEditing] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const archive = useArchiveItem(kind, id);

  if (item.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-12 w-80" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (item.error) return <ErrorState error={item.error} onRetry={() => void item.refetch()} />;
  const it = item.data;

  return (
    <>
      <PageHeader
        back={{ to: `/staff/${kind}`, label: KIND_TEXT[kind].title }}
        title={it.title}
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">
              {it.standard_name} · {it.board_code} · {it.subject_name}
            </Badge>
            {isTest(it) && (
              <span>
                {[
                  it.max_marks && `Max ${formatMarks(it.max_marks)} marks`,
                  `${it.duration_minutes} min`,
                  it.test_date && formatDate(it.test_date),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            )}
            {it.is_archived && <Badge tone="neutral">Archived</Badge>}
          </span>
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Edit details
            </Button>
            <Button variant="secondary" onClick={() => setConfirmArchive(true)}>
              {it.is_archived ? "Unarchive" : "Archive"}
            </Button>
          </>
        }
      />
      {(it.chapter_names as string[]).length > 0 && (
        <p className="text-sm text-muted">Chapters: {(it.chapter_names as string[]).join(", ")}</p>
      )}
      {it.description && <p className="max-w-3xl text-sm">{it.description}</p>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <FilesCard kind={kind} item={it} />
        <AssignmentsCard kind={kind} item={it} onAssign={() => setAssigning(true)} />
      </div>

      {assigning && !it.is_archived && (
        <AssignDialog
          kind={kind}
          item={it}
          alreadyAssigned={(assignments.data?.items ?? []).map((a) => a.student.id)}
          onClose={() => setAssigning(false)}
        />
      )}
      {editing && <EditItemDialog kind={kind} item={it} onClose={() => setEditing(false)} />}
      <ConfirmDialog
        open={confirmArchive}
        onOpenChange={setConfirmArchive}
        title={it.is_archived ? "Unarchive?" : "Archive?"}
        description={
          it.is_archived
            ? "It shows in the main list again and can be assigned."
            : "It's hidden from the main list and can't be assigned. Students who already have it keep it."
        }
        confirmLabel={it.is_archived ? "Unarchive" : "Archive"}
        tone="primary"
        pending={archive.isPending}
        onConfirm={() =>
          archive.mutate(!it.is_archived, {
            onSuccess: () => {
              setConfirmArchive(false);
              toast.success(it.is_archived ? "Unarchived." : "Archived.");
            },
            onError: (e) => toast.error(e.message),
          })
        }
      />
    </>
  );
}

function EditItemDialog({
  kind,
  item,
  onClose,
}: {
  kind: Kind;
  item: LearningItem;
  onClose: () => void;
}) {
  const update = useUpdateItem(kind, item.id);
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description ?? "");
  const [maxMarks, setMaxMarks] = useState(
    isTest(item) && item.max_marks ? formatMarks(item.max_marks) : "",
  );
  const [duration, setDuration] = useState(isTest(item) ? String(item.duration_minutes ?? "") : "");
  const [testDate, setTestDate] = useState(isTest(item) ? (item.test_date ?? "") : "");
  const [errors, setErrors] = useState<Record<string, string>>({});

  return (
    <Dialog open onOpenChange={(open) => !open && !update.isPending && onClose()}>
      <DialogContent title="Edit details">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = {
              title: title.trim(),
              description: description.trim(),
            };
            if (kind === "tests") {
              body.max_marks = maxMarks || null;
              body.duration_minutes = duration ? Number(duration) : undefined;
              body.test_date = testDate || null;
            }
            update.mutate(body, {
              onSuccess: () => {
                toast.success("Saved.");
                onClose();
              },
              onError: (err) => {
                if (err instanceof ApiError && Object.keys(err.fieldErrors).length) {
                  setErrors(
                    Object.fromEntries(
                      Object.entries(err.fieldErrors).map(([k, v]) => [k, v.join(" ")]),
                    ),
                  );
                } else toast.error(err.message);
              },
            });
          }}
        >
          <FormField label="Title" error={errors.title}>
            {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} />}
          </FormField>
          {kind === "tests" && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <FormField label="Max marks" error={errors.max_marks}>
                {(p) => (
                  <Input
                    {...p}
                    inputMode="decimal"
                    value={maxMarks}
                    onChange={(e) => setMaxMarks(e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Minutes" error={errors.duration_minutes}>
                {(p) => (
                  <Input
                    {...p}
                    inputMode="numeric"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Planned date" error={errors.test_date}>
                {(p) => (
                  <Input
                    {...p}
                    type="date"
                    value={testDate}
                    onChange={(e) => setTestDate(e.target.value)}
                  />
                )}
              </FormField>
            </div>
          )}
          <FormField label="Description">
            {(p) => (
              <Textarea
                {...p}
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            )}
          </FormField>
          <p className="text-xs text-muted">
            To change the class, subject or chapters, upload it again for the other class.
          </p>
          <div className="flex justify-end gap-2.5">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
