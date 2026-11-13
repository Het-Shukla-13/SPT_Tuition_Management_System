import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { MEDIUM_OPTIONS } from "@/lib/options";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ReferenceFilter } from "@/features/academics";
import type { Enquiry } from "@/lib/api/types";
import { formatPhone, formatRelativeDay } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { ENQUIRY_STATUSES, SOURCE_OPTIONS, sourceLabel, useEnquiries } from "../api";

const FILTERS = ["status", "source", "medium", "board", "standard"] as const;

const columns: ColumnDef<Enquiry, unknown>[] = [
  {
    id: "student",
    header: "Student",
    cell: ({ row }) => (
      <Link to={`/staff/enquiries/${row.original.id}`} className="flex flex-col">
        <b className="text-ink hover:text-primary hover:underline">{row.original.student_name}</b>
        <span className="text-xs text-muted">
          {[row.original.standard_name, row.original.board_code].filter(Boolean).join(" · ") ||
            "Standard not given"}
        </span>
      </Link>
    ),
  },
  {
    id: "parent",
    header: "Parent",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.parent_name}</span>
        <a
          href={`tel:${row.original.phone}`}
          className="tabular text-xs text-primary hover:underline"
        >
          {formatPhone(row.original.phone)}
        </a>
      </span>
    ),
  },
  {
    id: "message",
    header: "Message",
    cell: ({ row }) => (
      <span className="line-clamp-2 max-w-xs whitespace-normal text-muted">
        {row.original.message || "–"}
      </span>
    ),
  },
  {
    id: "source",
    header: "Came via",
    cell: ({ row }) => sourceLabel(row.original.source),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    id: "received",
    header: "Received",
    cell: ({ row }) => formatRelativeDay(row.original.created_at),
  },
];

/** Requests from the public "Ask about admission" form, newest first. */
export function EnquiriesPage() {
  const list = useListParams(FILTERS);
  const enquiries = useEnquiries(list.params);
  return (
    <>
      <PageHeader
        title="Enquiries"
        eyebrow="Families asking about admission: from the public form, or recorded here when they walk in or call."
        actions={
          <Button asChild>
            <Link to="/staff/enquiries/new">+ New enquiry</Link>
          </Button>
        }
      />
      <FilterBar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search name, phone or email"
        />
        <FilterSelect
          label="Status"
          allLabel="All statuses"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={ENQUIRY_STATUSES}
        />
        <FilterSelect
          label="Came via"
          allLabel="Any source"
          value={list.filters.source}
          onChange={(v) => list.setFilter("source", v)}
          options={SOURCE_OPTIONS}
        />
        <FilterSelect
          label="Medium"
          allLabel="Any medium"
          value={list.filters.medium}
          onChange={(v) => list.setFilter("medium", v)}
          options={MEDIUM_OPTIONS}
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
      </FilterBar>
      <DataTable
        caption="Admission enquiries"
        columns={columns}
        rows={enquiries.data?.items}
        meta={enquiries.data?.meta}
        loading={enquiries.isFetching && !enquiries.data}
        error={enquiries.error}
        onRetry={() => void enquiries.refetch()}
        onPageChange={list.setPage}
        rowKey={(e) => e.id}
        empty={{
          title: "No enquiries here",
          description:
            "They arrive from the form on the login page, or add one with + New enquiry.",
        }}
      />
    </>
  );
}
