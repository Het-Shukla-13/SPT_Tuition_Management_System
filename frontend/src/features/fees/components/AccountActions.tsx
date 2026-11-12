/** The less frequent changes to a fee account: adjustment, agreed fee, refund, reversal. */
import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import type { FeeAccountDetail, LedgerEntry } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

import {
  METHOD_OPTIONS,
  methodLabel,
  useAdjust,
  useChangeAgreedFee,
  useRefund,
  useReversePayment,
} from "../api";

const MONEY = /^\d+(\.\d{1,2})?$/;
const SIGNED_MONEY = /^-?\d+(\.\d{1,2})?$/;
const today = () => new Date().toLocaleDateString("en-CA");

function useFieldErrors() {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const fromApi = (err: Error) => {
    if (err instanceof ApiError && Object.keys(err.fieldErrors).length) {
      setErrors(
        Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v.join(" ")])),
      );
    } else toast.error(err.message);
  };
  return { errors, setErrors, fromApi };
}

function Footer({ pending, label, danger }: { pending: boolean; label: string; danger?: boolean }) {
  return (
    <div className="flex justify-end gap-2.5 pt-1">
      <DialogClose asChild>
        <Button variant="secondary" disabled={pending}>
          Cancel
        </Button>
      </DialogClose>
      <Button type="submit" variant={danger ? "danger" : "primary"} disabled={pending}>
        {pending ? "Saving…" : label}
      </Button>
    </div>
  );
}

type Props = { account: FeeAccountDetail; onClose: () => void };

export function AdjustmentDialog({ account, onClose }: Props) {
  const adjust = useAdjust(account.id);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [visible, setVisible] = useState(true);
  const { errors, setErrors, fromApi } = useFieldErrors();
  return (
    <Dialog open onOpenChange={(o) => !o && !adjust.isPending && onClose()}>
      <DialogContent
        title="Add adjustment"
        description="A discount or concession (negative) or an extra charge (positive)."
      >
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const next: Record<string, string> = {};
            if (!SIGNED_MONEY.test(amount) || Number(amount) === 0)
              next.amount = "Enter an amount, e.g. -2000 for a discount.";
            if (!reason.trim()) next.reason = "Say what it's for.";
            setErrors(next);
            if (Object.keys(next).length) return;
            adjust.mutate(
              { amount, reason: reason.trim(), visible_to_student: visible },
              {
                onSuccess: () => (toast.success("Adjustment added."), onClose()),
                onError: fromApi,
              },
            );
          }}
        >
          <FormField label="Amount (₹)" hint="Negative reduces what's owed." error={errors.amount}>
            {(p) => (
              <Input
                {...p}
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value.trim())}
                placeholder="-2000"
              />
            )}
          </FormField>
          <FormField label="Reason" error={errors.reason}>
            {(p) => (
              <Input
                {...p}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Sibling discount"
              />
            )}
          </FormField>
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
            <input
              type="checkbox"
              checked={visible}
              onChange={(e) => setVisible(e.target.checked)}
              className="size-5 accent-[var(--color-primary)]"
            />
            Show this line to the parent in the portal
          </label>
          <Footer pending={adjust.isPending} label="Add adjustment" />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function AgreedFeeDialog({ account, onClose }: Props) {
  const change = useChangeAgreedFee(account.id);
  const [fee, setFee] = useState(String(Number(account.agreed_fee)));
  const [reason, setReason] = useState("");
  const { errors, setErrors, fromApi } = useFieldErrors();
  return (
    <Dialog open onOpenChange={(o) => !o && !change.isPending && onClose()}>
      <DialogContent
        title="Change agreed fee"
        description="Recorded as a correction in the history; payments stay as they are."
      >
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const next: Record<string, string> = {};
            if (!MONEY.test(fee)) next.agreed_fee = "Enter an amount, e.g. 20000.";
            if (!reason.trim()) next.reason = "Say why it changed.";
            setErrors(next);
            if (Object.keys(next).length) return;
            change.mutate(
              { agreed_fee: fee, reason: reason.trim() },
              {
                onSuccess: () => (toast.success("Agreed fee changed."), onClose()),
                onError: fromApi,
              },
            );
          }}
        >
          <FormField
            label="New agreed fee (₹)"
            hint={
              <>
                Now <Money value={account.agreed_fee} />
              </>
            }
            error={errors.agreed_fee}
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
          <FormField label="Reason" error={errors.reason}>
            {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </FormField>
          <Footer pending={change.isPending} label="Change fee" />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function RefundDialog({ account, onClose }: Props) {
  const refund = useRefund(account.id);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("CASH");
  const [date, setDate] = useState(today);
  const [reason, setReason] = useState("");
  const { errors, setErrors, fromApi } = useFieldErrors();
  return (
    <Dialog open onOpenChange={(o) => !o && !refund.isPending && onClose()}>
      <DialogContent
        title="Refund"
        description={
          <>
            Money paid back to the family. Paid so far: <Money value={account.paid} />
          </>
        }
      >
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const next: Record<string, string> = {};
            if (!MONEY.test(amount) || Number(amount) <= 0)
              next.amount = "Enter an amount more than 0.";
            if (!reason.trim()) next.reason = "Say why.";
            setErrors(next);
            if (Object.keys(next).length) return;
            refund.mutate(
              { amount, method, entry_date: date, reason: reason.trim() },
              { onSuccess: () => (toast.success("Refund recorded."), onClose()), onError: fromApi },
            );
          }}
        >
          <FormField label="Amount (₹)" error={errors.amount}>
            {(p) => (
              <Input
                {...p}
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value.trim())}
              />
            )}
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Method">
              {(p) => (
                <NativeSelect {...p} value={method} onChange={(e) => setMethod(e.target.value)}>
                  {METHOD_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label="Date" error={errors.entry_date}>
              {(p) => (
                <Input
                  {...p}
                  type="date"
                  value={date}
                  max={today()}
                  onChange={(e) => setDate(e.target.value)}
                />
              )}
            </FormField>
          </div>
          <FormField label="Reason" error={errors.reason}>
            {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </FormField>
          <Footer pending={refund.isPending} label="Record refund" danger />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ReverseDialog({ entry, onClose }: { entry: LedgerEntry; onClose: () => void }) {
  const reverse = useReversePayment();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string>();
  return (
    <Dialog open onOpenChange={(o) => !o && !reverse.isPending && onClose()}>
      <DialogContent
        title="Reverse this payment?"
        description={
          <>
            <Money value={entry.amount} /> by {methodLabel(entry.method)} on{" "}
            {formatDate(entry.entry_date)}
            {entry.receipt_number && ` (${entry.receipt_number})`}. It stays in the history, marked
            reversed.
          </>
        }
      >
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (!reason.trim()) return setError("Say why, e.g. recorded for the wrong student.");
            reverse.mutate(
              { entryId: entry.id, reason: reason.trim() },
              {
                onSuccess: () => (toast.success("Payment reversed."), onClose()),
                onError: (err) => toast.error(err.message),
              },
            );
          }}
        >
          <FormField label="Reason" error={error}>
            {(p) => (
              <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            )}
          </FormField>
          <Footer pending={reverse.isPending} label="Reverse payment" danger />
        </form>
      </DialogContent>
    </Dialog>
  );
}
