import type { ReactNode } from "react";
import { toast } from "sonner";

import { Money } from "@/components/shared/Money";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { effectOnDue, ENTRY_LABEL, methodLabel, withRunningBalance } from "@/features/fees";
import { ApiError } from "@/lib/api/envelope";
import type { PortalFeeAccount } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import { openPortalReceipt, usePortalFees } from "../api";
import { PortalHeader } from "../components/PortalHeader";
import { useActiveStudent } from "../student";

/** Every year's fees, newest first, with each payment's receipt. Read-only: fees are paid at the institute. */
export function PortalFeesPage() {
  const { student } = useActiveStudent();
  const fees = usePortalFees(student.id);

  return (
    <div className="flex flex-col gap-4 p-4">
      <PortalHeader title="Fees" />
      <p className="text-sm text-muted">
        Fees are paid at Sai Personal Tuitions. Each payment here has a receipt you can open or
        save.
      </p>
      {fees.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : fees.error ? (
        <ErrorState error={fees.error} onRetry={() => void fees.refetch()} />
      ) : fees.data.length === 0 ? (
        <EmptyState title="No fees recorded yet" />
      ) : (
        fees.data.map((account) => (
          <YearCard key={account.id} studentId={student.id} account={account} />
        ))
      )}
    </div>
  );
}

function YearCard({ studentId, account }: { studentId: number; account: PortalFeeAccount }) {
  // Newest first reads best on a phone.
  const rows = withRunningBalance(account.entries, account.opening_balance).reverse();
  const receipt = (entryId: number) =>
    void openPortalReceipt(studentId, entryId).catch((e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Couldn't open the receipt."),
    );

  return (
    <Card className="gap-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-extrabold">{account.academic_year_name}</h2>
        <span className="flex gap-1.5">
          <StatusBadge status={account.status} />
          {account.is_overdue && <Badge tone="danger">Overdue</Badge>}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Total label="Total" value={<Money value={account.total} />} />
        <Total label="Paid" value={<Money value={account.paid} tone="paid" />} />
        <Total
          label={Number(account.credit) > 0 ? "Advance" : "Pending"}
          value={
            Number(account.credit) > 0 ? (
              <Money value={account.credit} />
            ) : (
              <Money
                value={account.pending}
                tone={Number(account.pending) > 0 ? "due" : undefined}
              />
            )
          }
        />
      </div>
      {Number(account.pending) > 0 && (
        <p className="text-sm text-muted">Due by {formatDate(account.due_date)}</p>
      )}

      <div className="flex flex-col">
        <h3 className="pb-1 text-sm font-bold text-muted">History</h3>
        <ul aria-label={`Fee history ${account.academic_year_name}`}>
          {rows.map(({ entry, balance }) => {
            const effect = effectOnDue(entry);
            return (
              <li key={entry.id} className="flex items-center gap-3 border-t border-line/70 py-3">
                <span className="flex min-w-0 flex-1 flex-col">
                  <b className="text-sm">
                    {ENTRY_LABEL[entry.entry_type] ?? entry.entry_type}
                    {entry.method && ` · ${methodLabel(entry.method)}`}
                  </b>
                  <span className="text-xs text-muted">
                    {[formatDate(entry.entry_date), entry.receipt_number, entry.remarks]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  <span className="text-xs text-muted">
                    Balance after: <Money value={balance} />
                  </span>
                </span>
                <span className="flex flex-col items-end gap-1">
                  <b className={cn("tabular", effect < 0 && "text-success")}>
                    {effect < 0 ? "−" : "+"}
                    <Money value={Math.abs(effect)} />
                  </b>
                  {entry.entry_type === "PAYMENT" && entry.receipt_number && (
                    <Button variant="ghost" size="sm" onClick={() => receipt(entry.id)}>
                      Receipt
                    </Button>
                  )}
                </span>
              </li>
            );
          })}
          {Number(account.opening_balance ?? 0) !== 0 && (
            <li className="flex items-center justify-between border-t border-line/70 py-3 text-sm">
              <b>Brought forward</b>
              <Money value={account.opening_balance} />
            </li>
          )}
        </ul>
      </div>
    </Card>
  );
}

function Total({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-[var(--radius-control)] bg-subtle py-2">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <span className="text-base font-extrabold">{value}</span>
    </div>
  );
}
