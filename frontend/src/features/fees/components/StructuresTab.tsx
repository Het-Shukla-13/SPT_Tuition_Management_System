import { useState } from "react";
import { toast } from "sonner";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar } from "@/components/shared/FilterBar";
import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ReferenceFilter, ReferenceSelect } from "@/features/academics";
import { ApiError } from "@/lib/api/envelope";
import type { FeeStructure } from "@/lib/api/types";
import { useListParams } from "@/lib/useListParams";

import { useFeeStructures, useSaveFeeStructure } from "../api";

const FILTERS = ["academic_year", "standard"] as const;

/** The standard fee per academic year + standard; admission suggests it as the agreed fee. */
export function StructuresTab() {
  const list = useListParams(FILTERS);
  const structures = useFeeStructures({ ...list.params, ordering: "standard__level" });
  const save = useSaveFeeStructure();
  const [editing, setEditing] = useState<FeeStructure | null | undefined>(undefined);

  const columns: ColumnDef<FeeStructure, unknown>[] = [
    {
      id: "year",
      header: "Year",
      cell: ({ row }) => `${row.original.board_code} ${row.original.academic_year_name}`,
    },
    { id: "standard", header: "Standard", cell: ({ row }) => <b>{row.original.standard_name}</b> },
    {
      id: "fee",
      header: "Yearly fee",
      meta: { align: "right" },
      cell: ({ row }) => <Money value={row.original.total_fee} />,
    },
    {
      id: "extras",
      header: "Optional subjects",
      cell: ({ row }) =>
        row.original.add_ons?.length ? (
          <span className="flex flex-col text-sm">
            {row.original.add_ons.map((a) => (
              <span key={a.subject}>
                {a.subject_name} +<Money value={a.amount} />
              </span>
            ))}
          </span>
        ) : (
          <span className="text-muted">–</span>
        ),
    },
    {
      id: "description",
      header: "Note",
      cell: ({ row }) => <span className="text-muted">{row.original.description || "–"}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.is_active ? "ACTIVE" : "INACTIVE"} />,
    },
    {
      id: "actions",
      header: "",
      meta: { align: "right" },
      cell: ({ row }) => (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => setEditing(row.original)}>
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              save.mutate(
                { id: row.original.id, body: { is_active: !row.original.is_active } },
                { onError: (e) => toast.error(e.message) },
              )
            }
          >
            {row.original.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </span>
      ),
    },
  ];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">
          The usual yearly fee for each board, year and standard, plus any extra fee for optional
          subjects like Gujarati or Hindi. On admission these are suggested and can still be changed
          per student.
        </p>
        <Button onClick={() => setEditing(null)}>+ Add fee structure</Button>
      </div>
      <FilterBar>
        <ReferenceFilter
          resource="academic-years"
          label="Academic year"
          allLabel="All years"
          value={list.filters.academic_year}
          onChange={(v) => list.setFilter("academic_year", v)}
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
        caption="Fee structures"
        columns={columns}
        rows={structures.data?.items}
        meta={structures.data?.meta}
        loading={structures.isFetching && !structures.data}
        error={structures.error}
        onRetry={() => void structures.refetch()}
        onPageChange={list.setPage}
        rowKey={(s) => s.id}
        empty={{
          title: "No fee structures yet",
          description: "Add the yearly fee for each standard.",
        }}
      />
      {editing !== undefined && (
        <StructureDialog structure={editing} onClose={() => setEditing(undefined)} />
      )}
    </>
  );
}

function StructureDialog({
  structure,
  onClose,
}: {
  structure: FeeStructure | null;
  onClose: () => void;
}) {
  const save = useSaveFeeStructure();
  const [year, setYear] = useState(structure ? String(structure.academic_year) : "");
  const [standard, setStandard] = useState(structure ? String(structure.standard) : "");
  const [fee, setFee] = useState(structure ? String(Number(structure.total_fee)) : "");
  const [description, setDescription] = useState(structure?.description ?? "");
  const [extras, setExtras] = useState<{ subject: string; amount: string }[]>(
    (structure?.add_ons ?? []).map((a) => ({
      subject: String(a.subject),
      amount: String(Number(a.amount)),
    })),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const setExtra = (i: number, patch: Partial<{ subject: string; amount: string }>) =>
    setExtras((list) => list.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  return (
    <Dialog open onOpenChange={(o) => !o && !save.isPending && onClose()}>
      <DialogContent title={structure ? "Edit fee structure" : "Add fee structure"}>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const next: Record<string, string> = {};
            if (!year) next.academic_year = "Choose the academic year.";
            if (!standard) next.standard = "Choose the standard.";
            if (!/^\d+(\.\d{1,2})?$/.test(fee))
              next.total_fee = "Enter the yearly fee, e.g. 22000.";
            const picked = extras.map((x) => x.subject);
            if (
              extras.some(
                (x) => !x.subject || !/^\d+(\.\d{1,2})?$/.test(x.amount) || Number(x.amount) <= 0,
              )
            )
              next.add_ons = "Choose a subject and enter an amount for each extra fee.";
            else if (new Set(picked).size !== picked.length)
              next.add_ons = "Each subject only once.";
            setErrors(next);
            if (Object.keys(next).length) return;
            save.mutate(
              {
                id: structure?.id,
                body: {
                  academic_year: Number(year),
                  standard: Number(standard),
                  total_fee: fee,
                  add_ons: extras.map((x) => ({ subject: Number(x.subject), amount: x.amount })),
                  description: description.trim(),
                },
              },
              {
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
              },
            );
          }}
        >
          <FormField label="Academic year" error={errors.academic_year ?? errors.non_field_errors}>
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="academic-years"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Standard" error={errors.standard}>
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="standards"
                value={standard}
                onChange={(e) => setStandard(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Yearly fee (₹)" error={errors.total_fee}>
            {(p) => (
              <Input
                {...p}
                inputMode="decimal"
                value={fee}
                onChange={(e) => setFee(e.target.value.trim())}
              />
            )}
          </FormField>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-[13px] font-bold">Extra fees for optional subjects</legend>
            <p className="text-xs text-muted">
              Charged only to students who take that subject, as a separate line on their fees.
            </p>
            {extras.map((x, i) => (
              <div key={i} className="flex items-center gap-2">
                <ReferenceSelect
                  aria-label={`Optional subject ${i + 1}`}
                  resource="subjects"
                  value={x.subject}
                  onChange={(e) => setExtra(i, { subject: e.target.value })}
                  placeholder="Subject…"
                />
                <span className="text-sm">₹</span>
                <Input
                  aria-label={`Extra fee ${i + 1}`}
                  inputMode="decimal"
                  value={x.amount}
                  onChange={(e) => setExtra(i, { amount: e.target.value.trim() })}
                  className="w-28 text-right"
                  placeholder="2000"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove extra fee ${i + 1}`}
                  onClick={() => setExtras((list) => list.filter((_, j) => j !== i))}
                >
                  ✕
                </Button>
              </div>
            ))}
            {errors.add_ons && (
              <p role="alert" className="text-sm text-danger">
                {errors.add_ons}
              </p>
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="self-start"
              onClick={() => setExtras((list) => [...list, { subject: "", amount: "" }])}
            >
              + Add optional subject fee
            </Button>
          </fieldset>
          <FormField label="Note (optional)">
            {(p) => (
              <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />
            )}
          </FormField>
          <div className="flex justify-end gap-2.5">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
