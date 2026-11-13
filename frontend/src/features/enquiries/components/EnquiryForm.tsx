import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import { MEDIUM_OPTIONS } from "@/lib/options";

import {
  type PublicEnquiryBody,
  SOURCE_OPTIONS,
  type StaffEnquiryBody,
  useEnquiryOptions,
} from "../api";

const schema = z.object({
  parent_name: z.string().trim().min(1, "Enter the parent's name."),
  phone: z
    .string()
    .trim()
    .regex(/^\+?[\d\s-]{10,16}$/, "Enter a 10-digit mobile number."),
  email: z.union([z.literal(""), z.email("Enter a valid email address.")]),
  student_name: z.string().trim().min(1, "Enter the student's name."),
  board: z.string(),
  standard: z.string(),
  medium: z.string(),
  school_name: z.string().max(200, "Keep it under 200 characters."),
  message: z.string().max(2000, "Keep it under 2000 characters."),
  website: z.string(), // honeypot (public form only): hidden from people, bots fill it
  source: z.string(),
  status: z.string(),
  notes: z.string(),
});
type Values = z.infer<typeof schema>;

const EMPTY: Values = {
  parent_name: "",
  phone: "",
  email: "",
  student_name: "",
  board: "",
  standard: "",
  medium: "",
  school_name: "",
  message: "",
  website: "",
  source: "WALK_IN",
  status: "CONTACTED",
  notes: "",
};

type Props =
  | { mode: "public"; onSubmit: (body: PublicEnquiryBody) => Promise<unknown> }
  | { mode: "staff"; onSubmit: (body: StaffEnquiryBody) => Promise<unknown> };

/**
 * The enquiry form: the public "Ask about admission" page, and staff recording a
 * family who walked in or phoned (staff also say how it came in, plus private notes).
 */
export function EnquiryForm(props: Props) {
  const options = useEnquiryOptions();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const errors = form.formState.errors;
  const staff = props.mode === "staff";

  const onSubmit = form.handleSubmit(async (v) => {
    const common = {
      parent_name: v.parent_name.trim(),
      phone: v.phone.trim(),
      email: v.email || undefined,
      student_name: v.student_name.trim(),
      board: v.board ? Number(v.board) : null,
      standard: v.standard ? Number(v.standard) : null,
      medium: v.medium,
      school_name: v.school_name.trim(),
      message: v.message.trim(),
    };
    try {
      if (props.mode === "staff") {
        await props.onSubmit({
          ...common,
          source: v.source,
          status: v.status,
          notes: v.notes.trim(),
        });
      } else {
        await props.onSubmit({ ...common, website: v.website });
      }
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      for (const [field, messages] of Object.entries(err.fieldErrors)) {
        if (field in v) form.setError(field as keyof Values, { message: messages.join(" ") });
      }
      if (!Object.keys(err.fieldErrors).length) form.setError("root", { message: err.message });
    }
  });

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-4" noValidate>
      {errors.root?.message && (
        <p
          role="alert"
          className="rounded-[var(--radius-control)] bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          {errors.root.message}
        </p>
      )}
      {staff && (
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Came via">
            {(p) => (
              <NativeSelect {...p} {...form.register("source")}>
                {SOURCE_OPTIONS.filter((s) => s.value !== "WEBSITE").map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Status">
            {(p) => (
              <NativeSelect {...p} {...form.register("status")}>
                <option value="CONTACTED">Contacted (spoke to them)</option>
                <option value="NEW">New (call back later)</option>
              </NativeSelect>
            )}
          </FormField>
        </div>
      )}
      <FormField label="Parent's name" error={errors.parent_name?.message}>
        {(p) => (
          <Input {...p} {...form.register("parent_name")} autoComplete={staff ? "off" : "name"} />
        )}
      </FormField>
      <FormField label="Mobile number" error={errors.phone?.message}>
        {(p) => (
          <Input
            {...p}
            {...form.register("phone")}
            type="tel"
            inputMode="tel"
            autoComplete={staff ? "off" : "tel"}
          />
        )}
      </FormField>
      <FormField label="Email (optional)" error={errors.email?.message}>
        {(p) => (
          <Input
            {...p}
            {...form.register("email")}
            type="email"
            autoComplete={staff ? "off" : "email"}
          />
        )}
      </FormField>
      <FormField label="Student's name" error={errors.student_name?.message}>
        {(p) => <Input {...p} {...form.register("student_name")} autoComplete="off" />}
      </FormField>
      <FormField label="School (optional)" error={errors.school_name?.message}>
        {(p) => (
          <Input
            {...p}
            {...form.register("school_name")}
            autoComplete="off"
            placeholder="e.g. Navrachana School"
          />
        )}
      </FormField>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <FormField label="Board (optional)">
          {(p) => (
            <NativeSelect {...p} {...form.register("board")} disabled={options.isPending}>
              <option value="">Not sure</option>
              {options.data?.boards.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <FormField label="Standard (optional)">
          {(p) => (
            <NativeSelect {...p} {...form.register("standard")} disabled={options.isPending}>
              <option value="">Not sure</option>
              {options.data?.standards.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <FormField label="Medium (optional)">
          {(p) => (
            <NativeSelect {...p} {...form.register("medium")}>
              <option value="">Not sure</option>
              {MEDIUM_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
      </div>
      <FormField label="Message (optional)" error={errors.message?.message}>
        {(p) => (
          <Textarea
            {...p}
            {...form.register("message")}
            rows={3}
            placeholder={
              staff
                ? "What they asked about: subjects, timings, fees…"
                : "Subjects, timings, questions…"
            }
          />
        )}
      </FormField>
      {staff ? (
        <FormField label="Notes (only staff see these)">
          {(p) => (
            <Textarea
              {...p}
              {...form.register("notes")}
              rows={2}
              placeholder="e.g. Will confirm after the trial class."
            />
          )}
        </FormField>
      ) : (
        // Honeypot: invisible to people and screen readers; bots that fill it are ignored.
        <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
          <label>
            Website
            <input tabIndex={-1} autoComplete="off" {...form.register("website")} />
          </label>
        </div>
      )}
      <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? "Saving…" : staff ? "Save enquiry" : "Send"}
      </Button>
    </form>
  );
}
