import { FileTextIcon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ApiError } from "@/lib/api/envelope";
import type { DocumentFile } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

import {
  type FileKind,
  type Kind,
  type LearningItem,
  openPdf,
  useRemoveAnswerKey,
  useReplaceFile,
  useVersions,
} from "../api";

const LABEL: Record<FileKind, string> = {
  PAPER: "Question paper",
  ANSWER_KEY: "Answer key",
  NOTE: "Notes PDF",
};
const sizeLabel = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;

const openFile = (kind: Kind, id: number, fileKind: FileKind, version?: number) =>
  openPdf(kind, id, fileKind, version).catch((e: unknown) =>
    toast.error(e instanceof ApiError ? e.message : "Couldn't open the file."),
  );

/** Current PDFs with open / replace (a new version; old ones are kept) and the answer key. */
export function FilesCard({ kind, item }: { kind: Kind; item: LearningItem }) {
  const files = (item.files ?? []) as DocumentFile[];
  const [showVersions, setShowVersions] = useState(false);
  const versions = useVersions(kind, item.id, showVersions);
  const mainKind: FileKind = kind === "tests" ? "PAPER" : "NOTE";
  const slots: FileKind[] = kind === "tests" ? ["PAPER", "ANSWER_KEY"] : [mainKind];

  return (
    <Card>
      <CardHeader
        title="Files"
        action={
          <Button variant="ghost" size="sm" onClick={() => setShowVersions((v) => !v)}>
            {showVersions ? "Hide versions" : "All versions"}
          </Button>
        }
      />
      <div className="flex flex-col gap-3">
        {slots.map((slot) => (
          <FileSlot
            key={slot}
            kind={kind}
            item={item}
            slot={slot}
            file={files.find((f) => f.kind === slot)}
          />
        ))}
      </div>
      {kind === "tests" && (
        <p className="text-[13px] text-muted">
          Students see the answer key only after their test ends (start time + duration). Replacing
          a file keeps the old version; students always get the newest.
        </p>
      )}
      {showVersions && (
        <ul className="flex flex-col border-t border-line pt-3 text-sm">
          {versions.isPending && <li className="text-muted">Loading…</li>}
          {versions.data?.map((v) => (
            <li key={v.id} className="flex items-center justify-between gap-3 py-1.5">
              <span>
                {LABEL[v.kind as FileKind]} v{v.version} · {v.original_name} ·{" "}
                {formatDateTime(v.uploaded_at)}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void openFile(kind, item.id, v.kind as FileKind, v.version)}
              >
                Open
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function FileSlot({
  kind,
  item,
  slot,
  file,
}: {
  kind: Kind;
  item: LearningItem;
  slot: FileKind;
  file?: DocumentFile;
}) {
  const replace = useReplaceFile(kind, item.id);
  const removeKey = useRemoveAnswerKey(item.id);
  const input = useRef<HTMLInputElement>(null);
  const [pendingDuplicate, setPendingDuplicate] = useState<File | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const upload = (picked: File, confirmDuplicate = false) => {
    if (picked.type !== "application/pdf" && !picked.name.toLowerCase().endsWith(".pdf")) {
      toast.error(`${picked.name} isn't a PDF.`);
      return;
    }
    replace.mutate(
      { file: picked, answerKey: slot === "ANSWER_KEY", confirmDuplicate },
      {
        onSuccess: () => {
          setPendingDuplicate(null);
          toast.success(file ? "New version uploaded." : `${LABEL[slot]} uploaded.`);
        },
        onError: (e) => {
          if (e instanceof ApiError && e.code === "DUPLICATE_DOCUMENT") setPendingDuplicate(picked);
          else toast.error(e.message);
        },
      },
    );
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-control)] border border-line px-3.5 py-3">
      <span className="flex min-w-0 items-center gap-3">
        <FileTextIcon className="size-5 shrink-0 text-muted" aria-hidden="true" />
        <span className="flex min-w-0 flex-col">
          <b>{LABEL[slot]}</b>
          <span className="truncate text-[13px] text-muted">
            {file
              ? `${file.original_name} · ${sizeLabel(file.size_bytes)} · v${file.version}`
              : "Not uploaded yet"}
          </span>
        </span>
      </span>
      <span className="flex gap-1">
        {file && (
          <Button variant="ghost" size="sm" onClick={() => void openFile(kind, item.id, slot)}>
            Open
          </Button>
        )}
        <Button
          variant="secondary"
          size="sm"
          disabled={replace.isPending}
          onClick={() => input.current?.click()}
        >
          {replace.isPending ? "Uploading…" : file ? "Replace" : "Upload"}
        </Button>
        {file && slot === "ANSWER_KEY" && (
          <Button
            variant="ghost"
            size="sm"
            className="text-danger"
            onClick={() => setConfirmRemove(true)}
          >
            Remove
          </Button>
        )}
      </span>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        className="sr-only"
        aria-label={`Choose a PDF for the ${LABEL[slot].toLowerCase()}`}
        onChange={(e) => {
          const picked = e.target.files?.[0];
          e.target.value = "";
          if (picked) upload(picked);
        }}
      />
      <ConfirmDialog
        open={pendingDuplicate !== null}
        onOpenChange={(open) => !open && setPendingDuplicate(null)}
        title="This exact PDF is already uploaded"
        description="Upload it again anyway?"
        confirmLabel="Upload anyway"
        tone="primary"
        pending={replace.isPending}
        onConfirm={() => pendingDuplicate && upload(pendingDuplicate, true)}
      />
      <ConfirmDialog
        open={confirmRemove}
        onOpenChange={setConfirmRemove}
        title="Remove the answer key?"
        description="Students won't see an answer key until you upload one again."
        confirmLabel="Remove"
        pending={removeKey.isPending}
        onConfirm={() =>
          removeKey.mutate(undefined, {
            onSuccess: () => {
              setConfirmRemove(false);
              toast.success("Answer key removed.");
            },
            onError: (e) => toast.error(e.message),
          })
        }
      />
    </div>
  );
}
