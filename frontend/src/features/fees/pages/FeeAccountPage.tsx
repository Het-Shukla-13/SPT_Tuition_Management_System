import { type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { Money } from "@/components/shared/Money";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError } from "@/lib/api/envelope";
import type { FeeAccountDetail, LedgerEntry } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import {
  effectOnDue,
  entryLabel,
  methodLabel,
  openReceipt,
  useFeeAccount,
  withRunningBalance,
} from "../api";
import {
  AdjustmentDialog,
  AgreedFeeDialog,
  RefundDialog,
  ReverseDialog,
} from "../components/AccountActions";
import { RecordPayment } from "../components/RecordPayment";

type Open = "adjust" | "agreed" | "refund" | null;

export function FeeAccountPage() {
  const id = Number(useParams().id);
  const account = useFeeAccount(id);
  const [open, setOpen] = useState<Open>(null);
  const [reversing, setReversing] = useState<LedgerEntry | null>(null);

  if (account.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-16 w-96" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }
  if (account.error)
    return <ErrorState error={account.error} onRetry={() => void account.refetch()} />;
  const a = account.data;

  return (
    <>
      <PageHeader
        back={{ to: "/staff/fees", label: "Fees" }}
        title={`Fees: ${a.student_name}`}
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <Link
              to={`/staff/students/${a.student}`}
              className="font-bold text-primary hover:underline"
            >
              {a.admission_number}
            </Link>
            · {a.board} {a.academic_year_name} · {a.standard} · due by {formatDate(a.due_date)}
            <StatusBadge status={String(a.status)} />
            {a.is_overdue && <Badge tone="danger">Overdue</Badge>}
          </span>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Total label="Total" value={<Money value={a.total} />} />
        <Total label="Paid" value={<Money value={a.paid} tone="paid" />} />
        <Total
          label="Pending"
          value={<Money value={a.pending} tone={Number(a.pending) > 0 ? "due" : undefined} />}
        />
        <Total label="Advance credit" value={<Money value={a.credit} />} />
      </div>

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Ledger account={a} onReverse={setReversing} onAction={setOpen} />
        <RecordPayment account={a} />
      </div>

      {open === "adjust" && <AdjustmentDialog account={a} onClose={() => setOpen(null)} />}
      {open === "agreed" && <AgreedFeeDialog account={a} onClose={() => setOpen(null)} />}
      {open === "refund" && <RefundDialog account={a} onClose={() => setOpen(null)} />}
      {reversing && <ReverseDialog entry={reversing} onClose={() => setReversing(null)} />}
    </>
  );
}

function Total({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      <span className="text-[22px] font-extrabold">{value}</span>
    </div>
  );
}

const receipt = (id: number) =>
  openReceipt(id).catch((e: unknown) =>
    toast.error(e instanceof ApiError ? e.message : "Couldn't open the receipt."),
  );

/** The account's history, oldest first, with what was owed after each line. */
function Ledger({
  account,
  onReverse,
  onAction,
}: {
  account: FeeAccountDetail;
  onReverse: (entry: LedgerEntry) => void;
  onAction: (open: Open) => void;
}) {
  const rows = withRunningBalance(account.entries, account.opening_balance);

  return (
    <Card className="gap-3 p-0">
      <CardHeader title="History" className="px-5 pt-5" />
      <p className="-mt-2 px-5 text-[13px] text-muted">
        Nothing is ever deleted: mistakes are reversed, so every rupee stays traceable.
      </p>
      <Table className="rounded-none border-x-0">
        <caption className="sr-only">Fee account history</caption>
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Entry</Th>
            <Th className="text-right">Amount</Th>
            <Th className="text-right">Balance due</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {Number(account.opening_balance) !== 0 && (
            <Tr>
              <Td>–</Td>
              <Td>
                Opening balance
                {account.opening_balance_reason ? ` · ${account.opening_balance_reason}` : ""}
              </Td>
              <Td className="tabular text-right">
                <Money value={account.opening_balance} />
              </Td>
              <Td className="tabular text-right">
                <Money value={account.opening_balance} />
              </Td>
              <Td />
            </Tr>
          )}
          {rows.map(({ entry, balance: after }) => {
            const effect = effectOnDue(entry);
            const isPayment = entry.entry_type === "PAYMENT";
            return (
              <Tr key={entry.id} className={cn(entry.reversed && "text-muted")}>
                <Td>{formatDate(entry.entry_date)}</Td>
                <Td className="whitespace-normal">
                  <span className="flex flex-col">
                    <span className="font-semibold">
                      {entryLabel(entry)}
                      {entry.method && ` · ${methodLabel(entry.method)}`}
                      {entry.reversed && (
                        <Badge tone="neutral" className="ml-2">
                          Reversed
                        </Badge>
                      )}
                    </span>
                    <span className="text-xs text-muted">
                      {[entry.receipt_number, entry.reference, entry.remarks]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                </Td>
                <Td
                  className={cn(
                    "tabular text-right font-bold",
                    effect < 0 && "text-success",
                    entry.reversed && "line-through",
                  )}
                >
                  {effect < 0 ? "−" : "+"}
                  <Money value={Math.abs(effect)} />
                </Td>
                <Td className="tabular text-right">
                  <Money value={after} />
                </Td>
                <Td className="text-right">
                  {isPayment && (
                    <span className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => void receipt(entry.id)}>
                        Receipt
                      </Button>
                      {!entry.reversed && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-danger"
                          onClick={() => onReverse(entry)}
                        >
                          Reverse
                        </Button>
                      )}
                    </span>
                  )}
                </Td>
              </Tr>
            );
          })}
        </tbody>
      </Table>
      <div className="flex flex-wrap gap-2 px-5 pb-5">
        <Button variant="secondary" size="sm" onClick={() => onAction("adjust")}>
          Add adjustment
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onAction("agreed")}>
          Change agreed fee
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onAction("refund")}>
          Refund
        </Button>
      </div>
    </Card>
  );
}
