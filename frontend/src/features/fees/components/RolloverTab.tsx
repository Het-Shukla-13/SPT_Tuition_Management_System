import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { EmptyState } from "@/components/shared/States";
import { Badge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { ReferenceSelect } from "@/features/academics";

import {
  ROLLOVER_ACTIONS,
  type RolloverAction,
  type RolloverResult,
  type RolloverRow,
  useRolloverApply,
  useRolloverPreview,
} from "../api";

type Choice = { action: RolloverAction; fee: string };
const KEEPS_STUDYING = (a: RolloverAction) => a === "PROMOTE" || a === "REPEAT";
const suggestedFee = (r: RolloverRow) =>
  r.suggested_agreed_fee ? String(Number(r.suggested_agreed_fee)) : "";
const suggested = (r: RolloverRow): Choice => ({
  action: r.suggested_action,
  fee: suggestedFee(r),
});

/**
 * Moves a board's students into the next academic year in one go: each is promoted,
 * repeats, leaves or completes, and any unpaid balance carries into the new account.
 */
export function RolloverTab() {
  const preview = useRolloverPreview();
  const apply = useRolloverApply();
  const [board, setBoard] = useState("");
  const [toYear, setToYear] = useState("");
  const [makeCurrent, setMakeCurrent] = useState(true);
  const [choices, setChoices] = useState<Record<number, Choice>>({});
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<RolloverResult | null>(null);

  const rows = preview.data ?? [];
  const pending = rows.filter((r) => !r.already_rolled_over);

  const load = () => {
    setResult(null);
    preview.mutate(
      { board: Number(board), to_year: Number(toYear) },
      {
        onSuccess: (data) =>
          setChoices(Object.fromEntries(data.map((r) => [r.student_id, suggested(r)]))),
        onError: (e) => toast.error(e.message),
      },
    );
  };

  const setChoice = (row: RolloverRow, next: Partial<Choice>) =>
    setChoices((c) => {
      const prev = c[row.student_id] ?? suggested(row);
      const merged = { ...prev, ...next };
      // Repeating keeps the old standard, so the next standard's suggested fee no longer fits.
      if (next.action === "REPEAT" && prev.action !== "REPEAT") merged.fee = "";
      if (next.action === "PROMOTE" && prev.action !== "PROMOTE") merged.fee = suggestedFee(row);
      return { ...c, [row.student_id]: merged };
    });

  const choiceOf = (r: RolloverRow) => choices[r.student_id] ?? suggested(r);

  const run = () =>
    apply.mutate(
      {
        board: Number(board),
        to_year: Number(toYear),
        make_current: makeCurrent,
        items: pending.map((r) => {
          const choice = choiceOf(r);
          return {
            student_id: r.student_id,
            action: choice.action,
            ...(KEEPS_STUDYING(choice.action) && choice.fee ? { agreed_fee: choice.fee } : {}),
          };
        }),
      },
      {
        onSuccess: (res) => {
          setConfirming(false);
          setResult(res);
          if (res.failed.length)
            toast.warning(`${res.done.length} done, ${res.failed.length} need attention.`);
          else toast.success(`Rolled over ${res.done.length} students.`);
          preview.mutate({ board: Number(board), to_year: Number(toYear) });
        },
        onError: (e) => {
          setConfirming(false);
          toast.error(e.message);
        },
      },
    );

  const names = Object.fromEntries(rows.map((r) => [r.student_id, r.name]));
  const badFee = pending.some((r) => {
    const c = choiceOf(r);
    return KEEPS_STUDYING(c.action) && c.fee !== "" && !/^\d+(\.\d{1,2})?$/.test(c.fee);
  });

  return (
    <>
      <p className="max-w-2xl text-sm text-muted">
        At the end of a board's year, choose what happens to each student. Unpaid balances carry
        into the new year's account automatically. Students already moved are skipped, so it's safe
        to run again.
      </p>
      <Card className="flex flex-row flex-wrap items-end gap-4 p-5">
        <div className="min-w-48">
          <FormField label="Board">
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="boards"
                value={board}
                onChange={(e) => {
                  setBoard(e.target.value);
                  setToYear("");
                  preview.reset();
                }}
              />
            )}
          </FormField>
        </div>
        <div className="min-w-48">
          <FormField label="Move into year">
            {(p) => (
              <ReferenceSelect
                {...p}
                resource="academic-years"
                filters={board ? { board } : undefined}
                disabled={!board}
                value={toYear}
                onChange={(e) => {
                  setToYear(e.target.value);
                  preview.reset();
                }}
              />
            )}
          </FormField>
        </div>
        <Button disabled={!board || !toYear || preview.isPending} onClick={load}>
          {preview.isPending ? "Loading…" : "Preview students"}
        </Button>
      </Card>

      {result && <ResultReport result={result} names={names} />}

      {preview.isSuccess &&
        (rows.length === 0 ? (
          <EmptyState title="No active students on this board" />
        ) : (
          <>
            <Table>
              <caption className="sr-only">Rollover preview</caption>
              <thead>
                <tr>
                  <Th>Student</Th>
                  <Th>Now in</Th>
                  <Th>What happens</Th>
                  <Th className="text-right">New yearly fee (₹)</Th>
                  <Th className="text-right">Balance to carry</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const choice = choiceOf(r);
                  const studying = KEEPS_STUDYING(choice.action);
                  return (
                    <Tr
                      key={r.student_id}
                      className={r.already_rolled_over ? "text-muted" : undefined}
                    >
                      <Td>
                        <span className="flex flex-col">
                          <b>{r.name}</b>
                          <span className="tabular text-xs text-muted">{r.admission_number}</span>
                        </span>
                      </Td>
                      <Td>{r.from_standard}</Td>
                      <Td>
                        {r.already_rolled_over ? (
                          <Badge tone="neutral">Already moved</Badge>
                        ) : (
                          <span className="flex items-center gap-2">
                            <NativeSelect
                              aria-label={`What happens to ${r.name}`}
                              value={choice.action}
                              onChange={(e) =>
                                setChoice(r, { action: e.target.value as RolloverAction })
                              }
                              className="w-auto"
                            >
                              {ROLLOVER_ACTIONS.filter(
                                (a) => a.value !== "PROMOTE" || r.to_standard,
                              ).map((a) => (
                                <option key={a.value} value={a.value}>
                                  {a.value === "PROMOTE" ? `Promote to ${r.to_standard}` : a.label}
                                </option>
                              ))}
                            </NativeSelect>
                          </span>
                        )}
                      </Td>
                      <Td className="text-right">
                        {!r.already_rolled_over && studying ? (
                          <Input
                            aria-label={`New yearly fee for ${r.name}`}
                            inputMode="decimal"
                            placeholder="Standard fee"
                            value={choice.fee}
                            onChange={(e) => setChoice(r, { fee: e.target.value.trim() })}
                            className="ml-auto w-32 text-right"
                          />
                        ) : (
                          "–"
                        )}
                      </Td>
                      <Td className="tabular text-right">
                        <Money
                          value={r.balance_to_carry}
                          tone={Number(r.balance_to_carry) > 0 ? "due" : undefined}
                        />
                      </Td>
                    </Tr>
                  );
                })}
              </tbody>
            </Table>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={makeCurrent}
                  onChange={(e) => setMakeCurrent(e.target.checked)}
                  className="size-4 accent-primary"
                />
                Also make this the board's current year
              </label>
              <Button disabled={pending.length === 0 || badFee} onClick={() => setConfirming(true)}>
                Roll over {pending.length} student{pending.length === 1 ? "" : "s"}
              </Button>
            </div>
            {badFee && (
              <p className="text-sm text-danger">
                Fix the fee amounts: use numbers like 22000, or leave blank for the standard fee.
              </p>
            )}
          </>
        ))}

      {confirming && (
        <Dialog open onOpenChange={(o) => !o && !apply.isPending && setConfirming(false)}>
          <DialogContent title="Roll over students?">
            <p className="text-sm">
              {summarise(pending.map((r) => choiceOf(r).action))} This creates new fee accounts and
              can't be undone in one step.
            </p>
            <div className="flex justify-end gap-2.5">
              <DialogClose asChild>
                <Button variant="secondary">Cancel</Button>
              </DialogClose>
              <Button disabled={apply.isPending} onClick={run}>
                {apply.isPending ? "Rolling over…" : "Roll over"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}

function summarise(actions: RolloverAction[]) {
  const parts = ROLLOVER_ACTIONS.map(
    (a) => [a.label.toLowerCase(), actions.filter((x) => x === a.value).length] as const,
  )
    .filter(([, n]) => n > 0)
    .map(([label, n]) => `${n} ${label}`);
  return `${parts.join(", ")}.`;
}

function ResultReport({
  result,
  names,
}: {
  result: RolloverResult;
  names: Record<number, string>;
}) {
  return (
    <Card className="gap-2 p-5" role="status">
      <b>
        {result.done.length} moved
        {result.failed.length ? `, ${result.failed.length} need attention` : ""}.
      </b>
      {result.failed.length > 0 && (
        <ul className="list-disc pl-5 text-sm">
          {result.failed.map((f) => (
            <li key={f.student_id}>
              <b>{names[f.student_id] ?? `Student #${f.student_id}`}</b>: {f.message}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
