import { zodResolver } from "@hookform/resolvers/zod";
import { XIcon } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Controller, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { ChipToggleGroup } from "@/components/shared/ChipToggleGroup";
import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { ReferenceSelect, useReferenceOptions } from "@/features/academics";
import { displayName } from "@/features/auth/session";
import { splitName, useEnquiry, useUpdateEnquiry } from "@/features/enquiries";
import { isAmount, shiftFee, toAmount, useCurrentStructure } from "@/features/fees";
import { ApiError } from "@/lib/api/envelope";
import type { AdminUser } from "@/lib/api/types";
import { formatDate, formatMoney } from "@/lib/format";
import { MEDIUM_OPTIONS } from "@/lib/options";
import type { Enquiry } from "@/lib/api/types";

import { type AdmissionBody, GENDER_OPTIONS, useAdmitStudent } from "../api";
import { ExistingLoginPicker } from "../components/ExistingLoginPicker";
import { GuardiansEditor } from "../components/GuardiansEditor";
import { OptionalSubjectFees } from "../components/OptionalSubjectFees";
import {
  cleanGuardians,
  emptyGuardian,
  type GuardianRow,
  guardianServerErrors,
  keptIndexes,
  validateGuardians,
} from "../guardians";
import {
  type ExtraChoice,
  type OptionalRow,
  optionalSubjectRows,
  type SubjectMove,
} from "../optionalSubjects";

const requiredId = (what: string) => z.string().min(1, `Choose a ${what}.`);

const schema = z
  .object({
    first_name: z.string().trim().min(1, "Enter the first name."),
    last_name: z.string().trim().min(1, "Enter the last name."),
    date_of_birth: z.string(),
    gender: z.string(),
    medium: z.string(),
    address: z.string(),
    board: requiredId("board"),
    standard: requiredId("standard"),
    school: requiredId("school"),
    admission_date: z.string(),
    subjects: z.array(z.number()).min(1, "Choose at least one subject."),
    agreed_fee: z
      .string()
      .trim()
      .refine(
        (v) => !v.startsWith("-"),
        "The standard fee can't go below zero: lower the optional amounts or raise it.",
      )
      .regex(/^(\d+(\.\d{1,2})?)?$/, "Enter an amount like 20000 or 20000.50."),
    opening_balance: z
      .string()
      .trim()
      .regex(/^(-?\d+(\.\d{1,2})?)?$/, "Enter an amount; negative for credit."),
    opening_balance_reason: z.string(),
    remarks: z.string(),
    new_logins: z.array(
      z.object({
        first_name: z.string().trim().min(1, "Enter the first name."),
        last_name: z.string().trim().min(1, "Enter the last name."),
        email: z.email("Enter the email they'll log in with."),
        phone: z.string(),
      }),
    ),
  })
  .refine(
    (v) => !v.opening_balance || Number(v.opening_balance) === 0 || v.opening_balance_reason.trim(),
    {
      path: ["opening_balance_reason"],
      message: "Say what the opening balance is for.",
    },
  );
type Values = z.infer<typeof schema>;

type Duplicate = {
  id: number;
  admission_number: string;
  name: string;
  standard: string;
  date_of_birth: string | null;
  status: string;
};

const EMPTY: Values = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  gender: "",
  medium: "",
  address: "",
  board: "",
  standard: "",
  school: "",
  admission_date: "",
  subjects: [],
  agreed_fee: "",
  opening_balance: "",
  opening_balance_reason: "",
  remarks: "",
  new_logins: [],
};

/** What an enquiry already tells us, so the office doesn't type it twice. */
function fromEnquiry(e: Enquiry): Values {
  const { first, last } = splitName(e.student_name);
  return {
    ...EMPTY,
    first_name: first,
    last_name: last,
    board: e.board ? String(e.board) : "",
    standard: e.standard ? String(e.standard) : "",
    medium: e.medium ?? "",
    remarks: e.message ? `From the enquiry: ${e.message}` : "",
  };
}

/** "New admission". With ?enquiry=<id> it starts from that enquiry and links the student to it. */
export function AdmissionPage() {
  const raw = useSearchParams()[0].get("enquiry");
  const enquiryId = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  const enquiry = useEnquiry(enquiryId);
  // Pre-filled dropdowns only keep their value if their options are there first.
  const boards = useReferenceOptions("boards", {}, enquiryId !== null);
  const standards = useReferenceOptions("standards", {}, enquiryId !== null);
  if (enquiryId !== null && (enquiry.isPending || boards.isPending || standards.isPending)) {
    return <Skeleton className="h-96 w-full" />;
  }
  // If the enquiry can't be loaded, still allow a normal admission.
  return enquiryId !== null && enquiry.data ? (
    <AdmissionForm
      initial={fromEnquiry(enquiry.data)}
      initialGuardians={[
        {
          name: enquiry.data.parent_name,
          relation: "",
          phone: enquiry.data.phone,
          email: enquiry.data.email ?? "",
        },
      ]}
      enquiry={enquiry.data}
    />
  ) : (
    <AdmissionForm initial={EMPTY} />
  );
}

/** The student, their class & subjects, the fee, and who can log in to see them. */
function AdmissionForm({
  initial,
  initialGuardians,
  enquiry,
}: {
  initial: Values;
  initialGuardians?: GuardianRow[];
  enquiry?: Enquiry;
}) {
  const [guardians, setGuardians] = useState<GuardianRow[]>(
    () => initialGuardians ?? [emptyGuardian()],
  );
  const [guardianErrors, setGuardianErrors] = useState<Record<string, string>>({});
  const navigate = useNavigate();
  const linkEnquiry = useUpdateEnquiry(enquiry?.id ?? 0);
  const admit = useAdmitStudent();
  const [linked, setLinked] = useState<AdminUser[]>([]);
  const [duplicates, setDuplicates] = useState<Duplicate[] | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: initial });
  const logins = useFieldArray({ control: form.control, name: "new_logins" });
  const subjects = useReferenceOptions("subjects");
  const errors = form.formState.errors;
  const openingBalance = useWatch({ control: form.control, name: "opening_balance" });
  const [board, standard, chosen] = useWatch({
    control: form.control,
    name: ["board", "standard", "subjects"],
  });
  const structure = useCurrentStructure(board, standard);
  const current = structure.data; // undefined: not known yet; null: none for this year/standard
  const [extras, setExtras] = useState<Record<number, ExtraChoice>>({});
  const [extrasError, setExtrasError] = useState<string | undefined>();
  // Per-student moves between included and optional, for the structure they were made against.
  const structureKey = current?.id ?? null;
  const [moveState, setMoveState] = useState<{
    key: number | null;
    moves: Record<number, SubjectMove>;
  }>({ key: null, moves: {} });
  const moves = moveState.key === structureKey ? moveState.moves : {};
  const setMoves = (next: Record<number, SubjectMove>) =>
    setMoveState({ key: structureKey, moves: next });
  const names: Record<number, string> = Object.fromEntries(
    (subjects.data ?? []).map((s) => [s.id, String(s.name)]),
  );
  const extraRows = optionalSubjectRows(current?.add_ons ?? [], chosen, extras, moves, names);
  const [firstName, agreedFee] = useWatch({
    control: form.control,
    name: ["first_name", "agreed_fee"],
  });

  // Staff's own ticks and typed fee win over the fee structure's suggestions.
  const subjectsTouched = useRef(false);
  const feeTouched = useRef(false);
  const prefilledFor = useRef<number | null>(null);
  useEffect(() => {
    if (current === undefined) return;
    const id = current?.id ?? null;
    if (id === prefilledFor.current) return;
    prefilledFor.current = id;
    if (current && !subjectsTouched.current && current.included_subjects?.length)
      form.setValue("subjects", current.included_subjects);
    if (!feeTouched.current)
      form.setValue("agreed_fee", current ? String(Number(current.total_fee)) : "");
  }, [current, form]);

  const fee = () => form.getValues("agreed_fee");
  const setFee = (value: string) =>
    form.setValue("agreed_fee", value, { shouldValidate: form.formState.isSubmitted });

  const optionalIds = new Set(extraRows.map((r) => r.subject));
  const covered = chosen.filter((id) => !optionalIds.has(id));
  const includedIds = current?.included_subjects ?? [];
  const includedName = (id: number) =>
    names[id] ?? current?.included_subject_names?.[includedIds.indexOf(id)] ?? "a subject";
  const missing = includedIds.filter((id) => !chosen.includes(id));
  const studentName = firstName.trim() || "This student";
  const charged = extraRows
    .filter((r) => r.choice.on)
    .reduce((t, r) => t + toAmount(r.choice.amount), 0);
  const yearTotal = isAmount(agreedFee) ? toAmount(agreedFee) + charged : null;
  const opening = /^-?\d+(\.\d{1,2})?$/.test(openingBalance.trim()) ? Number(openingBalance) : 0;

  /** An included subject charged separately: the amount typed comes off the standard fee. */
  const makeOptional = (id: number) => {
    const move = moves[id];
    if (move?.to === "included") {
      // It was optional in the structure: put its line back and take its amount out again.
      const rest = { ...moves };
      delete rest[id];
      setMoves(rest);
      setFee(shiftFee(fee(), -toAmount(move.amount)));
      const usual = current?.add_ons?.find((a) => a.subject === id)?.amount;
      setExtras((e) => ({
        ...e,
        // Waived before it was made included: waived again.
        [id]: move.amount
          ? { on: true, amount: move.amount }
          : { on: false, amount: usual ? String(Number(usual)) : "" },
      }));
      return;
    }
    setMoves({ ...moves, [id]: { to: "optional", amount: "" } });
  };

  /** Covered by the standard fee again: the row goes and its amount goes into the fee. */
  const makeIncluded = (row: OptionalRow) => {
    const amount = row.choice.on ? row.choice.amount : "";
    setFee(shiftFee(fee(), toAmount(amount)));
    const rest = { ...moves };
    if (row.moved) delete rest[row.subject];
    else rest[row.subject] = { to: "included", amount };
    setMoves(rest);
  };

  const changeRow = (row: OptionalRow, choice: ExtraChoice) => {
    if (!row.moved) {
      setExtras((e) => ({ ...e, [row.subject]: choice }));
      return;
    }
    // Keep a student taking everything paying the same: the fee moves with the amount.
    setFee(shiftFee(fee(), toAmount(row.choice.amount) - toAmount(choice.amount)));
    setMoves({ ...moves, [row.subject]: { to: "optional", amount: choice.amount } });
  };

  /** A dropped subject's move is undone, so its amount is back in the standard fee. */
  const changeSubjects = (next: number[]) => {
    subjectsTouched.current = true;
    const rest = { ...moves };
    let total = fee();
    for (const [key, move] of Object.entries(moves)) {
      const id = Number(key);
      if (next.includes(id)) continue;
      total = shiftFee(total, (move.to === "optional" ? 1 : -1) * toAmount(move.amount));
      delete rest[id];
    }
    if (Object.keys(rest).length !== Object.keys(moves).length) {
      setMoves(rest);
      setFee(total);
    }
    form.setValue("subjects", next, { shouldValidate: form.formState.isSubmitted });
  };

  const submit = async (values: Values, confirmDuplicate = false) => {
    const opt = (v: string) => v.trim() || undefined;
    const guardianProblems = validateGuardians(guardians);
    setGuardianErrors(guardianProblems);
    if (Object.keys(guardianProblems).length) return;
    const included = extraRows.filter((r) => r.choice.on);
    if (included.some((r) => !isAmount(r.choice.amount))) {
      setExtrasError("Enter amounts like 2000, or untick the subject.");
      return;
    }
    setExtrasError(undefined);
    if (current === null && !values.agreed_fee) {
      form.setError("agreed_fee", {
        message: "There's no fee structure for this standard yet: enter the standard fee.",
      });
      return;
    }
    const body: AdmissionBody = {
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
      date_of_birth: values.date_of_birth || null,
      gender: values.gender || undefined,
      medium: values.medium || undefined,
      address: opt(values.address),
      guardians: cleanGuardians(guardians),
      remarks: opt(values.remarks),
      board: Number(values.board),
      standard: Number(values.standard),
      school: Number(values.school),
      admission_date: values.admission_date || undefined,
      subjects: values.subjects,
      link_user_ids: linked.map((u) => u.id),
      new_logins: values.new_logins.map((l) => ({ ...l, phone: l.phone.trim() || undefined })),
      agreed_fee: values.agreed_fee || null,
      opening_balance: values.opening_balance || "0",
      opening_balance_reason: values.opening_balance_reason.trim(),
      // Once the fee structure is known, send exactly what staff chose (may be none).
      ...(current !== undefined && {
        subject_fees: included.map((r) => ({ subject: r.subject, amount: r.choice.amount })),
      }),
      confirm_duplicate: confirmDuplicate,
    };
    try {
      const result = await admit.mutateAsync(body);
      const invited = values.new_logins.length;
      toast.success(
        invited
          ? `${values.first_name} admitted. Invite email${invited > 1 ? "s" : ""} sent to set a password.`
          : `${values.first_name} admitted.`,
      );
      if (enquiry) {
        // Admitted: mark the enquiry and link it. A failure here mustn't hide the admission.
        await linkEnquiry
          .mutateAsync({ student: result.student.id })
          .catch(() =>
            toast.warning(
              "Admitted, but the enquiry couldn't be linked. Update it from Enquiries.",
            ),
          );
      }
      navigate(`/staff/students/${result.student.id}`);
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      if (err.code === "POSSIBLE_DUPLICATE_STUDENT") {
        setDuplicates(
          (err.errors as { possible_duplicates?: Duplicate[] })?.possible_duplicates ?? [],
        );
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      applyServerErrors(err);
    }
  };

  const applyServerErrors = (err: ApiError) => {
    const fields =
      err.errors && typeof err.errors === "object" ? (err.errors as Record<string, unknown>) : {};
    let shown = false;
    for (const [field, value] of Object.entries(fields)) {
      if (field === "new_logins" && Array.isArray(value)) {
        value.forEach((loginErrors, index) => {
          for (const [sub, messages] of Object.entries(
            (loginErrors ?? {}) as Record<string, string[]>,
          )) {
            form.setError(`new_logins.${index}.${sub}` as never, {
              message: [messages].flat().join(" "),
            });
            shown = true;
          }
        });
      } else if (field === "guardians") {
        setGuardianErrors(guardianServerErrors(fields, keptIndexes(guardians)));
        shown = true;
      } else if (field in EMPTY) {
        form.setError(field as keyof Values, { message: [value].flat().map(String).join(" ") });
        shown = true;
      }
    }
    if (!shown) toast.error(err.message);
  };

  return (
    <>
      <PageHeader
        back={{ to: "/staff/students", label: "Students" }}
        title="New admission"
        eyebrow={
          enquiry
            ? `Started from ${enquiry.parent_name}'s enquiry. Check the details, then fill in the rest.`
            : "Creates the student, their subjects, this year's fee account and the parent's login in one step."
        }
      />

      {duplicates && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-[var(--radius-card)] border border-warning/40 bg-warning-bg p-4 text-warning"
        >
          <b>This might be a student who's already admitted</b>
          <ul className="flex flex-col gap-1 text-sm">
            {duplicates.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/staff/students/${d.id}`}
                  target="_blank"
                  className="font-bold underline"
                >
                  {d.name}
                </Link>{" "}
                · {d.admission_number} · {d.standard}
                {d.date_of_birth && ` · born ${formatDate(d.date_of_birth)}`}
              </li>
            ))}
          </ul>
          <p className="text-sm">Siblings often look alike here. Check, then confirm.</p>
          <div className="flex flex-wrap gap-2.5">
            <Button
              className="bg-warning text-white hover:brightness-95"
              disabled={admit.isPending}
              onClick={form.handleSubmit((v) => submit(v, true))}
            >
              It's a different student: admit anyway
            </Button>
            <Button variant="secondary" onClick={() => setDuplicates(null)}>
              Let me check the details
            </Button>
          </div>
        </div>
      )}

      <form
        onSubmit={form.handleSubmit((v) => submit(v))}
        className="flex max-w-[1040px] flex-col gap-5"
        noValidate
      >
        <Section n={1} title="Student">
          <Grid>
            <FormField label="First name" error={errors.first_name?.message}>
              {(p) => <Input {...p} {...form.register("first_name")} autoComplete="off" />}
            </FormField>
            <FormField label="Last name" error={errors.last_name?.message}>
              {(p) => <Input {...p} {...form.register("last_name")} autoComplete="off" />}
            </FormField>
            <FormField label="Date of birth (optional)">
              {(p) => <Input {...p} {...form.register("date_of_birth")} type="date" />}
            </FormField>
            <FormField label="Gender (optional)">
              {(p) => (
                <NativeSelect {...p} {...form.register("gender")}>
                  <option value="">Not given</option>
                  {GENDER_OPTIONS.map((g) => (
                    <option key={g.value} value={g.value}>
                      {g.label}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          </Grid>
          <FormField label="Address (optional)">
            {(p) => <Textarea {...p} {...form.register("address")} rows={2} />}
          </FormField>
        </Section>

        <Section n={2} title="Academics">
          <Grid>
            <FormField label="Board" error={errors.board?.message}>
              {(p) => <ReferenceSelect {...p} {...form.register("board")} resource="boards" />}
            </FormField>
            <FormField label="Standard" error={errors.standard?.message}>
              {(p) => (
                <ReferenceSelect {...p} {...form.register("standard")} resource="standards" />
              )}
            </FormField>
            <FormField
              label="School"
              hint={
                <>
                  {enquiry?.school_name && (
                    <>
                      The enquiry says: <b className="text-ink">{enquiry.school_name}</b>.{" "}
                    </>
                  )}
                  Not listed?{" "}
                  <Link
                    to="/staff/academics?tab=schools"
                    target="_blank"
                    className="font-bold text-primary"
                  >
                    Add a school
                  </Link>
                </>
              }
              error={errors.school?.message}
            >
              {(p) => <ReferenceSelect {...p} {...form.register("school")} resource="schools" />}
            </FormField>
            <FormField label="Medium (optional)">
              {(p) => (
                <NativeSelect {...p} {...form.register("medium")}>
                  <option value="">Not given</option>
                  {MEDIUM_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label="Admission date" hint="Leave empty for today.">
              {(p) => <Input {...p} {...form.register("admission_date")} type="date" />}
            </FormField>
          </Grid>
          <Controller
            control={form.control}
            name="subjects"
            render={({ field }) => (
              <ChipToggleGroup
                label="Subjects"
                options={(subjects.data ?? []).map((s) => ({ value: s.id, label: String(s.name) }))}
                value={field.value}
                onChange={changeSubjects}
                loading={subjects.isPending}
                error={errors.subjects?.message}
              />
            )}
          />
        </Section>

        <Section n={3} title="Guardians">
          <p className="-mt-2 text-sm text-muted">
            Contacts the office can call, e.g. mother and father. They don't log in from here: add
            logins in step 5.
          </p>
          <GuardiansEditor value={guardians} onChange={setGuardians} errors={guardianErrors} />
        </Section>

        <Section n={4} title="Fee for this academic year">
          <Grid>
            <FormField
              label="Standard fee (without optional subjects)"
              hint={
                current
                  ? `From the fee structure: ${formatMoney(current.total_fee)} for the included subjects. Change it for this student if needed.`
                  : current === null
                    ? "No fee structure for this year and standard: enter the fee."
                    : "Filled in from the fee structure once the board and standard are chosen."
              }
              error={errors.agreed_fee?.message}
            >
              {(p) => (
                <Input
                  {...p}
                  {...form.register("agreed_fee", {
                    onChange: () => {
                      feeTouched.current = true;
                    },
                  })}
                  inputMode="decimal"
                  placeholder="e.g. 20000"
                />
              )}
            </FormField>
            <FormField
              label="Opening balance (₹, optional)"
              hint="Dues from before the app; negative for advance credit."
              error={errors.opening_balance?.message}
            >
              {(p) => <Input {...p} {...form.register("opening_balance")} inputMode="decimal" />}
            </FormField>
          </Grid>
          {current !== undefined && covered.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Covered by the standard fee</span>
              <ul className="flex flex-wrap gap-2">
                {covered.map((id) => (
                  <li
                    key={id}
                    className="flex items-center gap-1 rounded-full border border-line py-0.5 pr-1 pl-3 text-sm font-semibold"
                  >
                    {names[id] ?? includedName(id)}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Make ${names[id] ?? includedName(id)} optional`}
                      onClick={() => makeOptional(id)}
                    >
                      Make optional
                    </Button>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted">
                Only for this student: an optional subject gets its own line, and its amount comes
                off the standard fee. The fee structure doesn't change.
              </p>
            </div>
          )}
          {current && missing.length > 0 && (
            <p
              role="status"
              className="rounded-[var(--radius-control)] border border-warning/40 bg-warning-bg px-3 py-2 text-sm text-warning"
            >
              {`⚠ ${studentName} isn't taking ${missing.length} of the included subjects (${missing.map(includedName).join(", ")}). The standard fee covers all of them. Lower it if you're charging less.`}
            </p>
          )}
          <OptionalSubjectFees
            rows={extraRows}
            error={extrasError}
            onChange={changeRow}
            onMakeIncluded={makeIncluded}
          />
          {yearTotal !== null && (
            <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              <b>
                Total for {firstName.trim() || "this student"} this year: {formatMoney(yearTotal)}
              </b>
              {opening !== 0 && (
                <span className="text-muted">
                  Plus opening balance: {formatMoney(opening)} (not included above)
                </span>
              )}
            </p>
          )}
          {openingBalance && Number(openingBalance) !== 0 && (
            <FormField
              label="What is the opening balance for?"
              error={errors.opening_balance_reason?.message}
            >
              {(p) => <Input {...p} {...form.register("opening_balance_reason")} />}
            </FormField>
          )}
        </Section>

        <Section n={5} title="Who can log in to see this student">
          <p className="-mt-2 text-sm text-muted">
            Usually a parent. They get an email to set their own password. You can also add the
            student's own login, or link an existing parent (e.g. a sibling's).
          </p>
          {linked.length > 0 && (
            <ul className="flex flex-col gap-2">
              {linked.map((u) => (
                <li
                  key={u.id}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius-control)] bg-primary-tint px-3 py-2"
                >
                  <span>
                    <b>{displayName(u)}</b>{" "}
                    <span className="text-sm text-muted">
                      · {u.email ?? u.phone} · existing login
                    </span>
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Unlink ${displayName(u)}`}
                    onClick={() => setLinked((l) => l.filter((x) => x.id !== u.id))}
                  >
                    <XIcon />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {logins.fields.map((field, index) => (
            <div
              key={field.id}
              className="flex flex-col gap-3 rounded-[var(--radius-control)] border border-line p-4"
            >
              <div className="flex items-center justify-between">
                <b>New login {index + 1}</b>
                <Button variant="ghost" size="sm" onClick={() => logins.remove(index)}>
                  Remove
                </Button>
              </div>
              <Grid>
                <FormField
                  label="First name"
                  error={errors.new_logins?.[index]?.first_name?.message}
                >
                  {(p) => (
                    <Input
                      {...p}
                      {...form.register(`new_logins.${index}.first_name`)}
                      autoComplete="off"
                    />
                  )}
                </FormField>
                <FormField label="Last name" error={errors.new_logins?.[index]?.last_name?.message}>
                  {(p) => (
                    <Input
                      {...p}
                      {...form.register(`new_logins.${index}.last_name`)}
                      autoComplete="off"
                    />
                  )}
                </FormField>
                <FormField
                  label="Email"
                  hint="They log in with this."
                  error={errors.new_logins?.[index]?.email?.message}
                >
                  {(p) => (
                    <Input
                      {...p}
                      {...form.register(`new_logins.${index}.email`)}
                      type="email"
                      inputMode="email"
                      autoComplete="off"
                    />
                  )}
                </FormField>
                <FormField
                  label="Phone (optional)"
                  error={errors.new_logins?.[index]?.phone?.message}
                >
                  {(p) => (
                    <Input
                      {...p}
                      {...form.register(`new_logins.${index}.phone`)}
                      type="tel"
                      inputMode="tel"
                      autoComplete="off"
                    />
                  )}
                </FormField>
              </Grid>
            </div>
          ))}
          <div className="flex flex-wrap gap-2.5">
            <Button
              variant="secondary"
              onClick={() => {
                // Pre-fill each new login from the next guardian who has none yet.
                const g = guardians[logins.fields.length];
                const [first, ...rest] = (g?.name ?? "").trim().split(/\s+/);
                logins.append({
                  first_name: first ?? "",
                  last_name: rest.join(" "),
                  email: g?.email.trim() ?? "",
                  phone: g?.phone.trim() ?? "",
                });
              }}
            >
              + Add a new login
            </Button>
          </div>
          <ExistingLoginPicker
            exclude={linked.map((u) => u.id)}
            onPick={(u) => setLinked((l) => [...l, u])}
          />
        </Section>

        <Section n={6} title="Remarks (optional)">
          <FormField label="Anything the office should remember">
            {(p) => <Textarea {...p} {...form.register("remarks")} rows={2} />}
          </FormField>
        </Section>

        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 shadow-sm">
          <span className="text-sm text-muted">
            {logins.fields.length
              ? "Invite emails go out when you save."
              : "No login added: you can link one later from the profile."}
          </span>
          <div className="flex gap-2.5">
            <Button asChild variant="secondary">
              <Link to="/staff/students">Cancel</Link>
            </Button>
            <Button type="submit" disabled={admit.isPending}>
              {admit.isPending ? "Admitting…" : "Admit student"}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Card className="gap-4 p-5 sm:p-6">
      <div className="flex items-center gap-2.5">
        <span
          className="flex size-7 items-center justify-center rounded-full bg-primary text-sm font-extrabold text-white"
          aria-hidden="true"
        >
          {n}
        </span>
        <h2 className="text-lg font-extrabold">{title}</h2>
      </div>
      {children}
    </Card>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,220px),1fr))] gap-4">
      {children}
    </div>
  );
}
