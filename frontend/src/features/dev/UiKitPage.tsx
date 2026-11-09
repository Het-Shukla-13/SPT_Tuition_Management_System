import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { ActiveFilters, FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatCard } from "@/components/shared/StatCard";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";

type Row = {
  id: number;
  name: string;
  std: string;
  agreed: string;
  paid: string;
  pending: string;
  status: string;
};

const ROWS: Row[] = [
  {
    id: 1,
    name: "Aarav Shah",
    std: "Std 10 · CBSE",
    agreed: "20000.00",
    paid: "5000.00",
    pending: "15000.00",
    status: "DUE",
  },
  {
    id: 2,
    name: "Riya Shah",
    std: "Std 10 · CBSE",
    agreed: "20000.00",
    paid: "20000.00",
    pending: "0.00",
    status: "PAID",
  },
  {
    id: 3,
    name: "Isha Desai",
    std: "Std 10 · GSEB",
    agreed: "18000.00",
    paid: "9000.00",
    pending: "9000.00",
    status: "DUE",
  },
  {
    id: 4,
    name: "Arjun Rao",
    std: "Std 10 · CBSE",
    agreed: "22000.00",
    paid: "22000.00",
    pending: "0.00",
    status: "PAID",
  },
];

const COLUMNS: ColumnDef<Row, unknown>[] = [
  { header: "Student", accessorKey: "name", cell: (c) => <b>{c.getValue<string>()}</b> },
  { header: "Standard", accessorKey: "std" },
  {
    header: "Agreed",
    accessorKey: "agreed",
    meta: { align: "right" },
    cell: (c) => <Money value={c.getValue<string>()} />,
  },
  {
    header: "Paid",
    accessorKey: "paid",
    meta: { align: "right" },
    cell: (c) => <Money value={c.getValue<string>()} tone="paid" />,
  },
  {
    header: "Pending",
    accessorKey: "pending",
    meta: { align: "right" },
    cell: (c) => (
      <Money value={c.getValue<string>()} tone={Number(c.getValue()) > 0 ? "due" : undefined} />
    ),
  },
  {
    header: "Status",
    accessorKey: "status",
    cell: (c) => <StatusBadge status={c.getValue<string>()} />,
  },
];

/** Every shared component in one place, with sample data (dev only). */
export function UiKitPage() {
  const [search, setSearch] = useState("");
  const [board, setBoard] = useState("CBSE");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [page, setPage] = useState(1);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Component kit · sample data"
        title="Chalkboard components"
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => toast.success("Payment recorded. Receipt R-0533 created.")}
            >
              Show a toast
            </Button>
            <Button onClick={() => setConfirmOpen(true)}>Open confirm dialog</Button>
          </>
        }
      />

      <section className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
        <StatCard label="Active students" value="86" hint="+3 this month" />
        <StatCard
          label="Collected in November"
          value={<Money value="142500" />}
          hint="38 payments"
        />
        <StatCard
          label="Pending dues"
          value={<Money value="318000" />}
          tone="warning"
          hint="27 students"
        />
        <StatCard label="Loading example" value="0" loading />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-extrabold">DataTable + FilterBar</h2>
        <FilterBar>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search name, admission no., phone"
          />
          <FilterSelect
            label="Board"
            allLabel="All boards"
            value={board}
            onChange={setBoard}
            options={[
              { value: "CBSE", label: "CBSE" },
              { value: "GSEB", label: "GSEB" },
              { value: "ICSE", label: "ICSE" },
            ]}
          />
        </FilterBar>
        <ActiveFilters
          items={board ? [{ key: "board", label: board, onRemove: () => setBoard("") }] : []}
          onClearAll={() => setBoard("")}
        />
        <DataTable
          caption="Fee accounts"
          columns={COLUMNS}
          rows={ROWS}
          rowKey={(r) => r.id}
          meta={{
            page,
            page_size: 4,
            total_count: 41,
            total_pages: 11,
            has_next: page < 11,
            has_previous: page > 1,
          }}
          onPageChange={setPage}
        />
      </section>

      <section className="grid grid-cols-[repeat(auto-fit,minmax(360px,1fr))] gap-5">
        <Card>
          <CardHeader title="Form fields" />
          <FormField label="Amount (₹)" hint="Pending after this payment: ₹10,000">
            {(p) => <Input {...p} defaultValue="5,000" inputMode="decimal" />}
          </FormField>
          <FormField label="Parent's email" error="Enter a valid email address.">
            {(p) => <Input {...p} defaultValue="kavita@" />}
          </FormField>
          <FormField label="Method">
            {(p) => (
              <NativeSelect {...p} defaultValue="UPI">
                <option>Cash</option>
                <option>UPI</option>
                <option>Cheque</option>
              </NativeSelect>
            )}
          </FormField>
          <div className="flex flex-wrap gap-2.5">
            <Button>Save</Button>
            <Button variant="secondary">Cancel</Button>
            <Button variant="danger">Reverse</Button>
            <Button variant="ghost">View all</Button>
          </div>
        </Card>
        <Card>
          <CardHeader title="Badges" />
          <div className="flex flex-wrap gap-2">
            {[
              "ACTIVE",
              "PAID",
              "DUE",
              "OVERDUE",
              "UPCOMING",
              "ABSENT",
              "INVITED",
              "REVERSED",
              "LEFT",
            ].map((s) => (
              <StatusBadge key={s} status={s} />
            ))}
          </div>
          <CardHeader title="Money" className="pt-2" />
          <p className="flex flex-wrap gap-4 text-lg">
            <Money value="26000.00" /> <Money value="15000" tone="due" />{" "}
            <Money value="5000" tone="paid" />
          </p>
        </Card>
      </section>

      <section className="grid grid-cols-[repeat(auto-fit,minmax(360px,1fr))] gap-5">
        <EmptyState
          title="No students match these filters"
          description="Try another standard or clear the search."
          action={<Button variant="secondary">Clear filters</Button>}
        />
        <ErrorState
          error={
            new ApiError({
              status: 500,
              code: "INTERNAL_ERROR",
              message: "An unexpected error occurred. Please try again later.",
              requestId: "6f1c2a9d0b7e44c1",
            })
          }
          onRetry={() => toast("Retrying…")}
        />
      </section>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Reverse this payment?"
        description="₹5,000 by UPI on 2 Nov (R-0533). The receipt stays in history, marked reversed."
        confirmLabel="Reverse payment"
        onConfirm={() => {
          setConfirmOpen(false);
          toast.success("Payment reversed.");
        }}
      />
    </div>
  );
}
