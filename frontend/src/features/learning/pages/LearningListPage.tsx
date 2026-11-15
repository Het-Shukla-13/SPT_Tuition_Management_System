import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { ReferenceFilter, useYearNames } from "@/features/academics";
import { formatDate } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { KIND_TEXT } from "../text";
import {
  isTest,
  type Kind,
  type LearningItem,
  SEMESTER_OPTIONS,
  useBulkArchive,
  useItems,
} from "../api";

const FILTER_KEYS = [
  "board",
  "standard",
  "subject",
  "semester",
  "academic_year_name",
  "is_archived",
] as const;
// The backend shows only current (not archived) items unless asked.
const ARCHIVE_OPTIONS = [{ value: "true", label: "Archived" }];

function filesLabel(item: LearningItem) {
  const files = (item.files ?? []) as { kind: string; version: number }[];
  const main = files.find((f) => f.kind !== "ANSWER_KEY");
  const key = files.find((f) => f.kind === "ANSWER_KEY");
  if (!isTest(item)) return main ? `PDF v${main.version}` : "–";
  return key ? `Paper + key${key.version > 1 ? ` (v${key.version})` : ""}` : "Paper only";
}

export function LearningListPage({ kind }: { kind: Kind }) {
  const text = KIND_TEXT[kind];
  const list = useListParams(FILTER_KEYS);
  const items = useItems(kind, { ...list.params, ordering: "-created_at" });
  const years = useYearNames();
  const bulk = useBulkArchive(kind);
  const archivedView = list.filters.is_archived === "true";
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const pageIds = (items.data?.items ?? []).map((i) => i.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const toggle = (id: number) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const runBulk = () =>
    bulk.mutate(
      { ids: [...selected], archived: !archivedView },
      {
        onSuccess: (r) => {
          toast.success(`${archivedView ? "Unarchived" : "Archived"} ${r.done.length}.`);
          setSelected(new Set());
        },
        onError: (e) => toast.error(e.message),
      },
    );

  const columns: ColumnDef<LearningItem, unknown>[] = [
    {
      id: "select",
      header: () => (
        <input
          type="checkbox"
          aria-label="Select all on this page"
          checked={allOnPage}
          onChange={() =>
            setSelected((s) => {
              const next = new Set(s);
              pageIds.forEach((id) => (allOnPage ? next.delete(id) : next.add(id)));
              return next;
            })
          }
          className="size-4 accent-primary"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          aria-label={`Select ${row.original.title}`}
          checked={selected.has(row.original.id)}
          onChange={() => toggle(row.original.id)}
          className="size-4 accent-primary"
        />
      ),
    },
    {
      id: "title",
      header: kind === "tests" ? "Test" : "Notes",
      cell: ({ row }) => {
        const item = row.original;
        return (
          <Link to={`/staff/${kind}/${item.id}`} className="flex flex-col">
            <b className="text-ink hover:text-primary hover:underline">{item.title}</b>
            <span className="text-xs text-muted">
              {isTest(item)
                ? [
                    item.test_date && formatDate(item.test_date),
                    item.duration_minutes && `${item.duration_minutes} min`,
                    `${item.max_marks} marks`,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : `Uploaded ${formatDate(item.created_at)}`}
            </span>
          </Link>
        );
      },
    },
    {
      id: "boards",
      header: "Boards",
      cell: ({ row }) => row.original.board_codes.join(", ") || "All boards",
    },
    { id: "standard", header: "Standard", cell: ({ row }) => row.original.standard_name },
    { id: "subject", header: "Subject", cell: ({ row }) => row.original.subject_name },
    { id: "year", header: "Year", cell: ({ row }) => row.original.academic_year_name },
    {
      id: "chapters",
      header: "Chapters",
      cell: ({ row }) => (
        <span className="block max-w-[220px] truncate">
          {(row.original.chapter_names as string[]).join(", ") || "–"}
        </span>
      ),
    },
    { id: "files", header: "Files", cell: ({ row }) => filesLabel(row.original) },
    {
      id: "assigned",
      header: "Assigned",
      meta: { align: "right" },
      cell: ({ row }) =>
        row.original.is_archived ? (
          <Badge tone="neutral">Archived</Badge>
        ) : (
          `${row.original.active_assignments} students`
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title={text.title}
        eyebrow={text.intro}
        actions={
          <Button asChild>
            <Link to={`/staff/${kind}/new`}>+ Upload {text.singular}</Link>
          </Button>
        }
      />
      <FilterBar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search title, description, subject or chapter"
        />
        <ReferenceFilter
          resource="boards"
          label="Board"
          allLabel="All boards"
          value={list.filters.board}
          onChange={(v) => list.setFilter("board", v)}
        />
        <ReferenceFilter
          resource="standards"
          label="Standard"
          allLabel="All standards"
          value={list.filters.standard}
          onChange={(v) => list.setFilter("standard", v)}
        />
        <ReferenceFilter
          resource="subjects"
          label="Subject"
          allLabel="All subjects"
          value={list.filters.subject}
          onChange={(v) => list.setFilter("subject", v)}
        />
        <FilterSelect
          label="Semester"
          allLabel="Any semester"
          value={list.filters.semester}
          onChange={(v) => list.setFilter("semester", v)}
          options={SEMESTER_OPTIONS}
        />
        <FilterSelect
          label="Academic year"
          allLabel="All years"
          value={list.filters.academic_year_name}
          onChange={(v) => list.setFilter("academic_year_name", v)}
          options={years.names.map((n) => ({ value: n, label: n }))}
        />
        <FilterSelect
          label="Archive"
          allLabel="Current"
          value={list.filters.is_archived}
          onChange={(v) => {
            setSelected(new Set());
            list.setFilter("is_archived", v);
          }}
          options={ARCHIVE_OPTIONS}
        />
      </FilterBar>
      {selected.size > 0 && (
        <div
          role="region"
          aria-label="Selected"
          className="flex flex-wrap items-center gap-3 rounded-[var(--radius-control)] border border-line bg-surface px-4 py-2.5 text-sm"
        >
          <b>{selected.size} selected</b>
          <Button size="sm" variant="secondary" disabled={bulk.isPending} onClick={runBulk}>
            {archivedView ? "Unarchive" : "Archive"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      )}
      <DataTable
        caption={text.title}
        columns={columns}
        rows={items.data?.items}
        meta={items.data?.meta}
        loading={items.isFetching && !items.data}
        error={items.error}
        onRetry={() => void items.refetch()}
        onPageChange={list.setPage}
        rowKey={(i) => i.id}
        empty={{
          title: `No ${text.title.toLowerCase()} here`,
          description: "Change the filters, or upload one.",
          action: (
            <Button asChild variant="secondary">
              <Link to={`/staff/${kind}/new`}>+ Upload {text.singular}</Link>
            </Button>
          ),
        }}
      />
    </>
  );
}
