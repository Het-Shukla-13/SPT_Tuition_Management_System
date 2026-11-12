import { useId } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { Money } from "@/components/shared/Money";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import type { PaymentListItem } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { METHOD_OPTIONS, methodLabel, openReceipt, usePayments } from "../api";

const FILTERS = ["method", "entry_date__gte", "entry_date__lte"] as const;

const columns: ColumnDef<PaymentListItem, unknown>[] = [
  { id: "date", header: "Date", cell: ({ row }) => formatDate(row.original.entry_date) },
  {
    id: "student",
    header: "Student",
    cell: ({ row }) => (
      <Link to={`/staff/fees/accounts/${row.original.account}`} className="flex flex-col">
        <b className="text-ink hover:text-primary hover:underline">{row.original.student_name}</b>
        <span className="tabular text-xs text-muted">
          {row.original.admission_number} · {row.original.academic_year_name}
        </span>
      </Link>
    ),
  },
  {
    id: "method",
    header: "Method",
    cell: ({ row }) =>
      [methodLabel(row.original.method), row.original.reference].filter(Boolean).join(" · "),
  },
  {
    id: "receipt",
    header: "Receipt",
    cell: ({ row }) => <span className="tabular">{row.original.receipt_number ?? "–"}</span>,
  },
  {
    id: "amount",
    header: "Amount",
    meta: { align: "right" },
    cell: ({ row }) => (
      <span className="flex items-center justify-end gap-2">
        {row.original.reversed && <Badge tone="neutral">Reversed</Badge>}
        <span className={row.original.reversed ? "text-muted line-through" : "font-bold"}>
          <Money value={row.original.amount} />
        </span>
      </span>
    ),
  },
  {
    id: "open",
    header: "",
    meta: { align: "right" },
    cell: ({ row }) => (
      <Button
        variant="ghost"
        size="sm"
        onClick={() =>
          void openReceipt(row.original.id).catch((e: unknown) =>
            toast.error(e instanceof ApiError ? e.message : "Couldn't open it."),
          )
        }
      >
        PDF
      </Button>
    ),
  },
];

/** Every payment, newest first: a day's or month's collection at a glance. */
export function PaymentsTab() {
  const list = useListParams(FILTERS);
  const payments = usePayments({ ...list.params, ordering: "-entry_date" });
  return (
    <>
      <FilterBar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search student, admission no., receipt or reference"
        />
        <FilterSelect
          label="Method"
          allLabel="All methods"
          value={list.filters.method}
          onChange={(v) => list.setFilter("method", v)}
          options={METHOD_OPTIONS}
        />
        <DateFilter
          label="From"
          value={list.filters.entry_date__gte}
          onChange={(v) => list.setFilter("entry_date__gte", v)}
        />
        <DateFilter
          label="To"
          value={list.filters.entry_date__lte}
          onChange={(v) => list.setFilter("entry_date__lte", v)}
        />
      </FilterBar>
      <DataTable
        caption="Payments"
        columns={columns}
        rows={payments.data?.items}
        meta={payments.data?.meta}
        loading={payments.isFetching && !payments.data}
        error={payments.error}
        onRetry={() => void payments.refetch()}
        onPageChange={list.setPage}
        rowKey={(p) => p.id}
        empty={{ title: "No payments in this range" }}
      />
    </>
  );
}

function DateFilter({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <Label htmlFor={id} className="text-muted">
        {label}
      </Label>
      <Input
        id={id}
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-auto"
      />
    </div>
  );
}
