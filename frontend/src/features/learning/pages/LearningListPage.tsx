import { Link } from "react-router";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { ReferenceFilter } from "@/features/academics";
import { formatDate } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { KIND_TEXT } from "../text";
import { isTest, type Kind, type LearningItem, SEMESTER_OPTIONS, useItems } from "../api";

const FILTER_KEYS = [
  "board",
  "standard",
  "subject",
  "semester",
  "academic_year",
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

  const columns: ColumnDef<LearningItem, unknown>[] = [
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
      id: "class",
      header: "Class",
      cell: ({ row }) =>
        `${row.original.standard_name} · ${row.original.board_code} · ${row.original.subject_name}`,
    },
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
          label="Archive"
          allLabel="Current"
          value={list.filters.is_archived}
          onChange={(v) => list.setFilter("is_archived", v)}
          options={ARCHIVE_OPTIONS}
        />
      </FilterBar>
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
