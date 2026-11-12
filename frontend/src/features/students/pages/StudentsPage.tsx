import { Link } from "react-router";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { ReferenceFilter } from "@/features/academics";
import type { StudentListItem } from "@/lib/api/types";
import { formatPhone } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { STATUS_OPTIONS, studentName, useStudents } from "../api";

const FILTER_KEYS = ["board", "standard", "school", "status"] as const;

const columns: ColumnDef<StudentListItem, unknown>[] = [
  {
    id: "student",
    header: "Student",
    cell: ({ row }) => (
      <Link to={`/staff/students/${row.original.id}`} className="flex flex-col hover:text-primary">
        <b className="text-ink hover:text-primary hover:underline">{studentName(row.original)}</b>
        <span className="tabular text-xs text-muted">{row.original.admission_number}</span>
      </Link>
    ),
  },
  {
    id: "class",
    header: "Standard",
    cell: ({ row }) => `${row.original.standard.name} · ${row.original.board.code}`,
  },
  { id: "school", header: "School", cell: ({ row }) => row.original.school.name },
  {
    id: "parent",
    header: "Parent",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.guardian_name || "–"}</span>
        {row.original.guardian_phone && (
          <span className="text-xs text-muted">{formatPhone(row.original.guardian_phone)}</span>
        )}
      </span>
    ),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status ?? "ACTIVE"} />,
  },
];

export function StudentsPage() {
  const list = useListParams(FILTER_KEYS, { status: "ACTIVE" });
  const students = useStudents({ ...list.params, ordering: "first_name" });

  return (
    <>
      <PageHeader
        title="Students"
        eyebrow={students.data ? `${students.data.meta.total_count} matching` : undefined}
        actions={
          <Button asChild>
            <Link to="/staff/students/new">+ New admission</Link>
          </Button>
        }
      />
      <FilterBar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search name, admission no., parent's name or phone"
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
          resource="schools"
          label="School"
          allLabel="All schools"
          value={list.filters.school}
          onChange={(v) => list.setFilter("school", v)}
        />
        <FilterSelect
          label="Status"
          allLabel="Any status"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={STATUS_OPTIONS}
        />
      </FilterBar>
      <DataTable
        caption="Students"
        columns={columns}
        rows={students.data?.items}
        meta={students.data?.meta}
        loading={students.isFetching && !students.data}
        error={students.error}
        onRetry={() => void students.refetch()}
        onPageChange={list.setPage}
        rowKey={(s) => s.id}
        empty={{
          title: "No students match",
          description: "Try other filters, or admit a new student.",
          action: (
            <Button asChild variant="secondary">
              <Link to="/staff/students/new">+ New admission</Link>
            </Button>
          ),
        }}
      />
    </>
  );
}
