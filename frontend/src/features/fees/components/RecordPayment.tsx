import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { Money } from "@/components/shared/Money";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import type { FeeAccountDetail } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { METHOD_OPTIONS, openReceipt, useRecordPayment } from "../api";

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
const newKey = () => crypto.randomUUID();

/**
 * Record a payment. Each opened form has its own Idempotency-Key: pressing
 * Save twice (or a retry after a network hiccup) records the payment once.
 */
export function RecordPayment({ account }: { account: FeeAccountDetail }) {
  const record = useRecordPayment(account.id);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("UPI");
  const [date, setDate] = useState(today);
  const [reference, setReference] = useState("");
  const [remarks, setRemarks] = useState("");
  const [key, setKey] = useState(newKey);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const valid = /^\d+(\.\d{1,2})?$/.test(amount) && Number(amount) > 0;
  const after = valid ? Number(account.pending) - Number(amount) : null;

  const save = (event: React.FormEvent) => {
    event.preventDefault();
    if (!valid) {
      setErrors({ amount: "Enter an amount more than 0, e.g. 5000." });
      return;
    }
    setErrors({});
    record.mutate(
      {
        body: {
          amount,
          method,
          entry_date: date,
          reference: reference.trim(),
          remarks: remarks.trim(),
          visible_to_student: true,
        },
        idempotencyKey: key,
      },
      {
        onSuccess: (entry) => {
          toast.success(
            `Payment recorded${entry.receipt_number ? `: receipt ${entry.receipt_number}` : ""}.`,
            {
              action: { label: "Open receipt", onClick: () => void openReceipt(entry.id) },
            },
          );
          setAmount("");
          setReference("");
          setRemarks("");
          setKey(newKey()); // the next payment is a new one
        },
        onError: (err) => {
          if (err instanceof ApiError && Object.keys(err.fieldErrors).length) {
            setErrors(
              Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v.join(" ")])),
            );
          } else toast.error(err.message);
        },
      },
    );
  };

  const needsReference = method !== "CASH";
  return (
    <Card className="border-2 border-primary">
      <h2 className="text-lg font-extrabold">Record payment</h2>
      <form onSubmit={save} className="flex flex-col gap-4" noValidate>
        <FormField label="Amount (₹)" error={errors.amount}>
          {(p) => (
            <Input
              {...p}
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value.trim())}
              placeholder="e.g. 5000"
            />
          )}
        </FormField>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-[13px] font-bold">Method</legend>
          <div className="flex flex-wrap gap-2">
            {METHOD_OPTIONS.map((m) => (
              <label
                key={m.value}
                className={cn(
                  "inline-flex min-h-10 cursor-pointer items-center rounded-full border px-3.5 text-sm font-bold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary",
                  method === m.value
                    ? "border-primary bg-primary text-white"
                    : "border-line-strong bg-surface",
                )}
              >
                <input
                  type="radio"
                  name="method"
                  value={m.value}
                  checked={method === m.value}
                  onChange={() => setMethod(m.value)}
                  className="sr-only"
                />
                {m.label}
              </label>
            ))}
          </div>
        </fieldset>
        {needsReference && (
          <FormField
            label={
              method === "CHEQUE"
                ? "Cheque number"
                : method === "UPI"
                  ? "UPI reference"
                  : "Reference"
            }
            hint="Optional, helps match bank statements."
            error={errors.reference}
          >
            {(p) => (
              <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} />
            )}
          </FormField>
        )}
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
        <FormField label="Note (optional)">
          {(p) => <Input {...p} value={remarks} onChange={(e) => setRemarks(e.target.value)} />}
        </FormField>
        <Button type="submit" size="lg" disabled={record.isPending}>
          {record.isPending ? "Saving…" : "Save & create receipt"}
        </Button>
        <p className="text-xs text-muted">
          Pressing Save twice records it only once.
          {after !== null && (
            <>
              {" "}
              {after >= 0 ? "Pending after this payment: " : "Advance credit after this payment: "}
              <b className="text-ink">
                <Money value={Math.abs(after)} />
              </b>
            </>
          )}
        </p>
      </form>
    </Card>
  );
}
