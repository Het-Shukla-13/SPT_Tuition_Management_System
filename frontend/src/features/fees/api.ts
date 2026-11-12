/**
 * Fees (backend: /api/v1/admin/..., FAQ §9). Admin only.
 * The ledger is append-only: nothing is edited or deleted; mistakes are
 * reversed, so every rupee stays traceable.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { openFile } from "@/lib/api/openFile";
import type {
  FeeAccountDetail,
  FeeAccountListItem,
  FeeStructure,
  LedgerEntry,
  PaymentListItem,
} from "@/lib/api/types";
import { listQueryOptions } from "@/lib/useListParams";

const FEES = ["admin", "fees"] as const;
const accountUrl = (id: number) => `admin/fees/accounts/${id}/`;

export function useFeeAccounts(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...FEES, "accounts", params],
    queryFn: () => api.list<FeeAccountListItem>("admin/fees/accounts/", params),
    ...listQueryOptions,
  });
}

export function useFeeAccount(id: number) {
  return useQuery({
    queryKey: [...FEES, "account", id],
    queryFn: () => api.get<FeeAccountDetail>(accountUrl(id)),
  });
}

export function usePayments(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...FEES, "payments", params],
    queryFn: () => api.list<PaymentListItem>("admin/fees/payments/", params),
    ...listQueryOptions,
  });
}

export function useFeeStructures(params: Record<string, string | number>) {
  return useQuery({
    queryKey: [...FEES, "structures", params],
    queryFn: () => api.list<FeeStructure>("admin/fee-structures/", params),
    ...listQueryOptions,
  });
}

/** Every fee change refreshes all fee data (accounts, payments, the student's summary). */
function useFeeMutation<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FEES }),
  });
}

export type PaymentBody = {
  amount: string;
  method: string;
  entry_date: string;
  reference?: string;
  remarks?: string;
  visible_to_student?: boolean;
};

/**
 * Record a payment. The Idempotency-Key makes a double-click or a network
 * retry record it ONCE: same key = the same payment comes back.
 */
export const useRecordPayment = (accountId: number) =>
  useFeeMutation(({ body, idempotencyKey }: { body: PaymentBody; idempotencyKey: string }) =>
    api.post<LedgerEntry>(`${accountUrl(accountId)}payments/`, body, {
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  );

export const useAdjust = (accountId: number) =>
  useFeeMutation((body: { amount: string; reason: string; visible_to_student: boolean }) =>
    api.post<LedgerEntry>(`${accountUrl(accountId)}adjustments/`, body),
  );

export const useChangeAgreedFee = (accountId: number) =>
  useFeeMutation((body: { agreed_fee: string; reason: string }) =>
    api.post<FeeAccountDetail>(`${accountUrl(accountId)}agreed-fee/`, body),
  );

export const useRefund = (accountId: number) =>
  useFeeMutation(
    (body: {
      amount: string;
      method: string;
      entry_date: string;
      reference?: string;
      reason: string;
    }) => api.post<LedgerEntry>(`${accountUrl(accountId)}refunds/`, body),
  );

export const useReversePayment = () =>
  useFeeMutation(({ entryId, reason }: { entryId: number; reason: string }) =>
    api.post<LedgerEntry>(`admin/fees/entries/${entryId}/reverse/`, { reason }),
  );

export const useSaveFeeStructure = () =>
  useFeeMutation(({ id, body }: { id?: number; body: Record<string, unknown> }) =>
    id
      ? api.patch<FeeStructure>(`admin/fee-structures/${id}/`, body)
      : api.post<FeeStructure>("admin/fee-structures/", body),
  );

// ── Year-end rollover ──────────────────────────────────────────────────
export type RolloverAction = "PROMOTE" | "REPEAT" | "LEAVE" | "COMPLETE";
export type RolloverRow = {
  student_id: number;
  admission_number: string;
  name: string;
  from_standard: string;
  suggested_action: RolloverAction;
  to_standard: string | null;
  suggested_agreed_fee: string | null;
  balance_to_carry: string;
  already_rolled_over: boolean;
};
export type RolloverResult = {
  done: { student_id: number; action: string }[];
  failed: { student_id: number; reason: string; message: string }[];
};

export const useRolloverPreview = () =>
  useMutation({
    mutationFn: (body: { board: number; to_year: number }) =>
      api.post<RolloverRow[]>("admin/rollover/preview/", body),
  });

export const useRolloverApply = () =>
  useFeeMutation(
    (body: {
      board: number;
      to_year: number;
      make_current: boolean;
      items: { student_id: number; action: RolloverAction; agreed_fee?: string | null }[];
    }) => api.post<RolloverResult>("admin/rollover/apply/", body),
  );

/** Open a payment receipt PDF in a new tab. */
export const openReceipt = (entryId: number) => openFile(`admin/fees/payments/${entryId}/receipt/`);

export const METHOD_OPTIONS = [
  { value: "CASH", label: "Cash" },
  { value: "UPI", label: "UPI" },
  { value: "BANK_TRANSFER", label: "Bank transfer" },
  { value: "CHEQUE", label: "Cheque" },
  { value: "OTHER", label: "Other" },
];
export const methodLabel = (value: string | null | undefined) =>
  METHOD_OPTIONS.find((m) => m.value === value)?.label ?? "";

export const ENTRY_LABEL: Record<string, string> = {
  CHARGE: "Agreed fee",
  ADJUSTMENT: "Adjustment",
  PAYMENT: "Payment",
  REVERSAL: "Payment reversed",
  REFUND: "Refund",
  CARRY_OUT: "Carried to next year",
};

/** How an entry changes what's owed: payments reduce it; everything else is stored signed. */
export const effectOnDue = (entry: { entry_type: string; amount: string }) =>
  entry.entry_type === "PAYMENT" ? -Number(entry.amount) : Number(entry.amount);

type DatedEntry = {
  id: number;
  entry_type: string;
  amount: string;
  entry_date?: string;
  created_at?: string;
};

/** Entries oldest first, each with what was still owed after it. */
export function withRunningBalance<T extends DatedEntry>(
  entries: T[],
  openingBalance: string | undefined,
) {
  const sorted = [...entries].sort(
    (x, y) =>
      (x.entry_date ?? "").localeCompare(y.entry_date ?? "") ||
      (x.created_at ?? "").localeCompare(y.created_at ?? "") ||
      x.id - y.id,
  );
  const rows: { entry: T; balance: number }[] = [];
  sorted.reduce(
    (due, entry) => {
      const balance = due + effectOnDue(entry);
      rows.push({ entry, balance });
      return balance;
    },
    Number(openingBalance ?? 0),
  );
  return rows;
}

export const ROLLOVER_ACTIONS: { value: RolloverAction; label: string }[] = [
  { value: "PROMOTE", label: "Promote" },
  { value: "REPEAT", label: "Repeat standard" },
  { value: "LEAVE", label: "Left" },
  { value: "COMPLETE", label: "Completed" },
];
