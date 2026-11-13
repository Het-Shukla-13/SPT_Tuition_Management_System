import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";

import { Money } from "@/components/shared/Money";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/envelope";
import type { FeeAccountDetail, FeeAccountListItem } from "@/lib/api/types";

import { subjectFeesOnAccount, useChangeSubjectFee, useFeeAccount, useStructureFor } from "../api";

type Subject = { id: number; name: string };
type Row = { subject: Subject; action: "ADD" | "REMOVE"; amount: string; on: boolean };

/**
 * After a student's subjects change mid-year: offer to add the extra fee for an
 * optional subject they started, or take off the fee for one they dropped.
 * Pre-filled from the fee structure / the account; staff confirm, edit or skip.
 */
export function SubjectFeeFollowUp({
  studentId,
  standardId,
  added,
  dropped,
  onClose,
}: {
  studentId: number;
  standardId: number;
  added: Subject[];
  dropped: Subject[];
  onClose: () => void;
}) {
  const accounts = useQuery({
    queryKey: ["admin", "fees", "student", studentId],
    queryFn: () => api.get<FeeAccountListItem[]>(`admin/fees/students/${studentId}/accounts/`),
  });
  // Newest year first: the one this change belongs to.
  const latest = accounts.data?.[0];
  const account = useFeeAccount(latest?.id ?? 0, !!latest);
  const structure = useStructureFor(latest?.academic_year, standardId);

  if (accounts.isPending || (latest && (account.isPending || structure.isPending))) {
    return (
      <Shell onClose={onClose}>
        <Skeleton className="h-24 w-full" />
      </Shell>
    );
  }
  if (!latest || !account.data) return <Nothing onClose={onClose} />;

  const charged = subjectFeesOnAccount(account.data.entries);
  const extras = new Map((structure.data?.add_ons ?? []).map((a) => [a.subject, a.amount]));
  const rows: Row[] = [
    ...added
      .filter((s) => extras.has(s.id) && !(charged.get(s.id)! > 0))
      .map((s) => ({
        subject: s,
        action: "ADD" as const,
        amount: String(Number(extras.get(s.id))),
        on: true,
      })),
    ...dropped
      .filter((s) => (charged.get(s.id) ?? 0) > 0)
      .map((s) => ({
        subject: s,
        action: "REMOVE" as const,
        amount: String(charged.get(s.id)),
        on: true,
      })),
  ];
  if (rows.length === 0) return <Nothing onClose={onClose} />;
  return <Choices account={account.data} initial={rows} onClose={onClose} />;
}

function Choices({
  account,
  initial,
  onClose,
}: {
  account: FeeAccountDetail;
  initial: Row[];
  onClose: () => void;
}) {
  const change = useChangeSubjectFee(account.id);
  const [rows, setRows] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const update = (i: number, patch: Partial<Row>) =>
    setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  const apply = async () => {
    const chosen = rows.filter((r) => r.on);
    if (chosen.some((r) => !/^\d+(\.\d{1,2})?$/.test(r.amount) || Number(r.amount) <= 0)) {
      return setError("Enter amounts like 2000.");
    }
    setError(null);
    try {
      for (const r of chosen) {
        await change.mutateAsync({ subject: r.subject.id, action: r.action, amount: r.amount });
      }
      if (chosen.length) toast.success("Fees updated.");
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update the fees.");
    }
  };

  return (
    <Shell onClose={onClose} pending={change.isPending}>
      <p className="text-sm">
        These subjects have their own fee in {account.board} {account.academic_year_name}. Untick
        any you don't want to change.
      </p>
      <ul className="flex flex-col gap-3">
        {rows.map((r, i) => (
          <li key={r.subject.id} className="flex flex-wrap items-center gap-3">
            <label className="flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                checked={r.on}
                onChange={(e) => update(i, { on: e.target.checked })}
                className="size-4 accent-primary"
              />
              {r.action === "ADD"
                ? `Add the ${r.subject.name} fee`
                : `Take off the ${r.subject.name} fee`}
            </label>
            <span className="flex items-center gap-1 text-sm">
              ₹
              <Input
                aria-label={`${r.subject.name} amount`}
                inputMode="decimal"
                value={r.amount}
                disabled={!r.on}
                onChange={(e) => update(i, { amount: e.target.value.trim() })}
                className="w-28 text-right"
              />
            </span>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2.5">
        <DialogClose asChild>
          <Button variant="secondary" disabled={change.isPending}>
            Skip
          </Button>
        </DialogClose>
        <Button onClick={() => void apply()} disabled={change.isPending}>
          {change.isPending ? "Updating…" : "Update fees"}
        </Button>
      </div>
      <p className="text-xs text-muted">
        Pending now: <Money value={account.pending} />. Each change shows as its own line in the fee
        history.
      </p>
    </Shell>
  );
}

function Shell({
  children,
  onClose,
  pending,
}: {
  children: ReactNode;
  onClose: () => void;
  pending?: boolean;
}) {
  return (
    <Dialog open onOpenChange={(o) => !o && !pending && onClose()}>
      <DialogContent title="Update this year's fees?">{children}</DialogContent>
    </Dialog>
  );
}

/** No optional-subject fee is affected: nothing to ask, so close straight away. */
function Nothing({ onClose }: { onClose: () => void }) {
  useEffect(() => onClose(), [onClose]);
  return null;
}
