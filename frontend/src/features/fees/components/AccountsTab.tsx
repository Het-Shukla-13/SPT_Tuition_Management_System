import { Link } from "react-router";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { Money } from "@/components/shared/Money";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { ReferenceFilter } from "@/features/academics";
import type { FeeAccountListItem } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { useFeeAccounts } from "../api";

const FILTERS = ["academic_year", "academic_year__board", "student__standard", "ordering"] as const;
const SORT_OPTIONS = [
  { value: "-pending", label: "Highest pending first" },
  { value: "student__first_name", label: "Name A–Z" },
  { value: "-last_payment_date", label: "Recently paid" },
  { value: "student__standard__level", label: "Standard" },
];

const columns: ColumnDef<FeeAccountListItem, unknown>[] = [
  {
    id: "student",
    header: "Student",
    cell: ({ row }) => (
      <Link to={`/staff/fees/accounts/${row.original.id}`} className="flex flex-col">
        <b className="text-ink hover:text-primary hover:underline">{row.original.student_name}</b>
        <span className="tabular text-xs text-muted">{row.original.admission_number}</span>
      </Link>
    ),
  },
  {
    id: "class",
    header: "Year · standard",
    cell: ({ row }) =>
      `${row.original.board} ${row.original.academic_year_name} · ${row.original.standard}`,
  },
  {
    id: "total",
    header: "Total",
    meta: { align: "right" },
    cell: ({ row }) => <Money value={row.original.total} />,
  },
  {
    id: "paid",
    header: "Paid",
    meta: { align: "right" },
    cell: ({ row }) => <Money value={row.original.paid} tone="paid" />,
  },
  {
    id: "pending",
    header: "Pending",
    meta: { align: "right" },
    cell: ({ row }) => (
      <Money
        value={row.original.pending}
        tone={Number(row.original.pending) > 0 ? "due" : undefined}
      />
    ),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <span className="flex gap-1.5">
        <StatusBadge status={String(row.original.status)} />
        {row.original.is_overdue && <Badge tone="danger">Overdue</Badge>}
      </span>
    ),
  },
  {
    id: "last",
    header: "Last payment",
    cell: ({ row }) => (
      <span className="text-muted">
        {row.original.last_payment_date ? formatDate(row.original.last_payment_date) : "–"}
      </span>
    ),
  },
];

/** Every student's fee account, highest dues first by default. */
export function AccountsTab() {
  const list = useListParams(FILTERS, { ordering: "-pending" });
  const accounts = useFeeAccounts(list.params);
  return (
    <>
      <FilterBar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search student, admission no., parent phone"
        />
        <ReferenceFilter
          resource="academic-years"
          label="Academic year"
          allLabel="All years"
          value={list.filters.academic_year}
          onChange={(v) => list.setFilter("academic_year", v)}
        />
        <ReferenceFilter
          resource="boards"
          label="Board"
          allLabel="All boards"
          value={list.filters.academic_year__board}
          onChange={(v) => list.setFilter("academic_year__board", v)}
        />
        <ReferenceFilter
          resource="standards"
          label="Standard"
          allLabel="All standards"
          value={list.filters.student__standard}
          onChange={(v) => list.setFilter("student__standard", v)}
        />
        <FilterSelect
          label="Sort"
          allLabel="Highest pending first"
          value={list.filters.ordering === "-pending" ? "" : list.filters.ordering}
          onChange={(v) => list.setFilter("ordering", v || "-pending")}
          options={SORT_OPTIONS.slice(1)}
        />
      </FilterBar>
      <DataTable
        caption="Fee accounts"
        columns={columns}
        rows={accounts.data?.items}
        meta={accounts.data?.meta}
        loading={accounts.isFetching && !accounts.data}
        error={accounts.error}
        onRetry={() => void accounts.refetch()}
        onPageChange={list.setPage}
        rowKey={(a) => a.id}
        empty={{
          title: "No fee accounts match",
          description: "Fee accounts are created when a student is admitted.",
        }}
      />
    </>
  );
}
