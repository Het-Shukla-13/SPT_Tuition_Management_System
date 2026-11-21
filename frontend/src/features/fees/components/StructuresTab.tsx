import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { FilterBar } from "@/components/shared/FilterBar";
import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { ReferenceFilter, ReferenceSelect, useReferenceOptions } from "@/features/academics";
import { ApiError } from "@/lib/api/envelope";
import type { FeeStructure } from "@/lib/api/types";
import { useListParams } from "@/lib/useListParams";

import { useFeeStructures, useSaveFeeStructure } from "../api";
import { isAmount, shiftFee, toAmount } from "../feeMath";
import { asYears, yearsOfBoard } from "../years";
import { YearNameFilter } from "./YearNameFilter";

const FILTERS = ["academic_year__board", "academic_year__name", "standard"] as const;

/** An optional subject's extra fee; `moved`: taken out of the included subjects in this form. */
type Extra = { subject: string; amount: string; moved?: boolean };

/** The standard fee per academic year + standard; admission suggests it as the agreed fee. */
export function StructuresTab() {
  const list = useListParams(FILTERS);
  const structures = useFeeStructures({ ...list.params, ordering: "standard__level" });
  const save = useSaveFeeStructure();
  const [editing, setEditing] = useState<FeeStructure | null | undefined>(undefined);

  const columns: ColumnDef<FeeStructure, unknown>[] = [
    { id: "board", header: "Board", cell: ({ row }) => row.original.board_code },
    { id: "year", header: "Year", cell: ({ row }) => row.original.academic_year_name },
    { id: "standard", header: "Standard", cell: ({ row }) => <b>{row.original.standard_name}</b> },
    {
      id: "fee",
      header: "Standard fee",
      meta: { align: "right" },
      cell: ({ row }) => <Money value={row.original.total_fee} />,
    },
    {
      id: "included",
      header: "Included subjects",
      cell: ({ row }) =>
        row.original.included_subject_names?.length ? (
          <span className="text-sm">{row.original.included_subject_names.join(", ")}</span>
        ) : (
          <span className="text-muted">–</span>
        ),
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
          The standard yearly fee for each board, year and standard, covering its included subjects,
          plus any extra fee for optional subjects like Gujarati or Hindi. On admission these are
          suggested and can still be changed per student.
        </p>
        <Button onClick={() => setEditing(null)}>+ Add fee structure</Button>
      </div>
      <FilterBar>
        <ReferenceFilter
          resource="boards"
          label="Board"
          allLabel="All boards"
          value={list.filters.academic_year__board}
          onChange={(v) => list.setFilter("academic_year__board", v)}
        />
        <YearNameFilter
          value={list.filters.academic_year__name}
          onChange={(v) => list.setFilter("academic_year__name", v)}
          board={list.filters.academic_year__board}
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
  const yearOptions = useReferenceOptions("academic-years");
  const allYears = asYears(yearOptions.data);
  const [pickedBoard, setPickedBoard] = useState("");
  // Editing: the structure's board comes from its year.
  const board =
    pickedBoard ||
    (structure ? String(allYears.find((y) => y.id === structure.academic_year)?.board ?? "") : "");
  const [year, setYear] = useState(structure ? String(structure.academic_year) : "");
  const boardYears = board ? yearsOfBoard(allYears, board) : [];
  const [standard, setStandard] = useState(structure ? String(structure.standard) : "");
  const [fee, setFee] = useState(structure ? String(Number(structure.total_fee)) : "");
  const [description, setDescription] = useState(structure?.description ?? "");
  const [extras, setExtras] = useState<Extra[]>(
    (structure?.add_ons ?? []).map((a) => ({
      subject: String(a.subject),
      amount: String(Number(a.amount)),
    })),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const subjects = useReferenceOptions("subjects");
  // New structures start with the main subjects included, once they've loaded.
  const [pickedIncluded, setPickedIncluded] = useState<number[] | null>(
    structure ? (structure.included_subjects ?? []) : null,
  );
  const included =
    pickedIncluded ?? (subjects.data ?? []).filter((s) => s.is_main).map((s) => s.id);
  const subjectName = (id: string) =>
    String(subjects.data?.find((s) => String(s.id) === id)?.name ?? "this subject");

  /** Ticking an included subject that's listed as optional moves it back (and its amount). */
  const changeIncluded = (next: number[]) => {
    let rows = extras;
    let total = fee;
    for (const id of next.filter((n) => !included.includes(n))) {
      const row = rows.find((x) => x.subject === String(id));
      if (!row) continue;
      total = shiftFee(total, toAmount(row.amount));
      rows = rows.filter((x) => x !== row);
    }
    setExtras(rows);
    setFee(total);
    setPickedIncluded(next);
  };

  /**
   * Choosing an included subject as optional takes it out of the included ones,
   * and its amount comes off the standard fee: a student taking everything pays the same.
   */
  const changeExtraSubject = (i: number, subject: string) => {
    const row = extras[i];
    if (!row) return;
    let inc = included;
    let total = fee;
    if (row.moved && row.subject) {
      inc = [...inc, Number(row.subject)];
      total = shiftFee(total, toAmount(row.amount));
    }
    const moved = !!subject && inc.includes(Number(subject));
    if (moved) {
      inc = inc.filter((id) => id !== Number(subject));
      total = shiftFee(total, -toAmount(row.amount));
    }
    setExtras(extras.map((x, j) => (j === i ? { ...x, subject, moved } : x)));
    setPickedIncluded(inc);
    setFee(total);
  };

  const changeExtraAmount = (i: number, amount: string) => {
    const row = extras[i];
    if (!row) return;
    if (row.moved) setFee(shiftFee(fee, toAmount(row.amount) - toAmount(amount)));
    setExtras(extras.map((x, j) => (j === i ? { ...x, amount } : x)));
  };

  /** Back into the included subjects: its amount goes back into the standard fee. */
  const makeIncluded = (i: number) => {
    const row = extras[i];
    if (!row) return;
    setPickedIncluded([...included, Number(row.subject)]);
    setFee(shiftFee(fee, toAmount(row.amount)));
    setExtras(extras.filter((_, j) => j !== i));
  };

  const allIncluded = isAmount(fee) ? toAmount(fee) : null;
  const everything =
    allIncluded === null ? null : allIncluded + extras.reduce((t, x) => t + toAmount(x.amount), 0);

  return (
    <Dialog open onOpenChange={(o) => !o && !save.isPending && onClose()}>
      <DialogContent title={structure ? "Edit fee structure" : "Add fee structure"}>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const next: Record<string, string> = {};
            if (!board) next.board = "Choose the board.";
            else if (!year) next.academic_year = "Choose the academic year.";
            if (!standard) next.standard = "Choose the standard.";
            if (fee.trim().startsWith("-"))
              next.total_fee =
                "The standard fee can't go below zero: lower the optional amounts or raise it.";
            else if (!isAmount(fee)) next.total_fee = "Enter the standard fee, e.g. 22000.";
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
                  included_subjects: included,
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
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Board" error={errors.board}>
              {(p) => (
                <ReferenceSelect
                  {...p}
                  resource="boards"
                  value={board}
                  onChange={(e) => {
                    setPickedBoard(e.target.value);
                    // Start from that board's current year.
                    const own = yearsOfBoard(allYears, e.target.value);
                    setYear(String((own.find((y) => y.is_current) ?? own[0])?.id ?? ""));
                  }}
                />
              )}
            </FormField>
            <FormField
              label="Academic year"
              error={errors.academic_year ?? errors.non_field_errors}
            >
              {(p) => (
                <NativeSelect
                  {...p}
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  disabled={!board}
                >
                  <option value="">{board ? "Choose…" : "Pick a board first"}</option>
                  {boardYears.map((y) => (
                    <option key={y.id} value={y.id}>
                      {y.name}
                      {y.is_current ? " (current)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          </div>
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
          <ChipToggleGroup
            label="Included subjects (covered by the standard fee)"
            options={(subjects.data ?? []).map((s) => ({ value: s.id, label: String(s.name) }))}
            value={included}
            onChange={changeIncluded}
            loading={subjects.isPending}
            error={errors.included_subjects}
          />
          <FormField
            label="Standard fee (for the included subjects)"
            hint="What a student taking all the included subjects pays for the year."
            error={errors.total_fee}
          >
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
              Picking an included subject here moves it out of the included ones and takes its
              amount off the standard fee.
            </p>
            {extras.map((x, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <ReferenceSelect
                  aria-label={`Optional subject ${i + 1}`}
                  resource="subjects"
                  value={x.subject}
                  onChange={(e) => changeExtraSubject(i, e.target.value)}
                  placeholder="Subject…"
                />
                <span className="text-sm">₹</span>
                <Input
                  aria-label={`Extra fee ${i + 1}`}
                  inputMode="decimal"
                  value={x.amount}
                  onChange={(e) => changeExtraAmount(i, e.target.value.trim())}
                  className="w-28 text-right"
                  placeholder="2000"
                />
                {x.subject && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Make ${subjectName(x.subject)} included`}
                    onClick={() => makeIncluded(i)}
                  >
                    Make included
                  </Button>
                )}
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
            <p className="text-xs text-muted">
              Subject not listed?{" "}
              <Link
                to="/staff/academics?tab=subjects"
                target="_blank"
                className="font-bold text-primary hover:underline"
              >
                Add a subject
              </Link>{" "}
              in Academics setup, then pick it here.
            </p>
          </fieldset>
          {allIncluded !== null && (
            <div
              aria-label="Yearly totals"
              className="flex flex-col gap-1 rounded-[var(--radius-control)] bg-subtle px-3 py-2 text-sm"
            >
              <span>
                Student taking all included subjects: <Money value={allIncluded} />
              </span>
              {extras.length > 0 && (
                <span>
                  Also taking every optional subject: <Money value={everything} />
                </span>
              )}
            </div>
          )}
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
