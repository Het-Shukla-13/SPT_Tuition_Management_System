import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeftIcon, CheckCircle2Icon } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { AuthHeading, AuthLayout, FormAlert } from "@/features/auth/components/AuthLayout";
import { ApiError } from "@/lib/api/envelope";

import { useEnquiryOptions, useSubmitEnquiry } from "../api";

const schema = z.object({
  parent_name: z.string().trim().min(1, "Enter your name."),
  phone: z
    .string()
    .trim()
    .regex(/^\+?[\d\s-]{10,16}$/, "Enter a 10-digit mobile number."),
  email: z.union([z.literal(""), z.email("Enter a valid email address.")]),
  student_name: z.string().trim().min(1, "Enter the student's name."),
  board: z.string(),
  standard: z.string(),
  message: z.string().max(2000, "Keep it under 2000 characters."),
  website: z.string(), // honeypot: hidden from people, bots fill it
});
type Values = z.infer<typeof schema>;

/** Public, no login: a family asks about admission and the institute calls back. */
export function PublicEnquiryPage() {
  const options = useEnquiryOptions();
  const submit = useSubmitEnquiry();
  const [done, setDone] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      parent_name: "",
      phone: "",
      email: "",
      student_name: "",
      board: "",
      standard: "",
      message: "",
      website: "",
    },
  });
  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await submit.mutateAsync({
        parent_name: v.parent_name.trim(),
        phone: v.phone.trim(),
        email: v.email || undefined,
        student_name: v.student_name.trim(),
        board: v.board ? Number(v.board) : null,
        standard: v.standard ? Number(v.standard) : null,
        message: v.message.trim(),
        website: v.website,
      });
      setDone(v.parent_name.trim());
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, messages] of Object.entries(err.fieldErrors)) {
          if (field in v) form.setError(field as keyof Values, { message: messages.join(" ") });
        }
      }
    }
  });

  if (done) {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-3 text-center" role="status">
          <CheckCircle2Icon className="size-12 text-success" aria-hidden="true" />
          <AuthHeading
            title={`Thank you, ${done}!`}
            subtitle="Sai Personal Tuitions will call you back soon."
          />
          <Link to="/login" className="flex min-h-11 items-center text-sm font-bold text-primary">
            Back to log in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  const failure =
    submit.error instanceof ApiError && !Object.keys(submit.error.fieldErrors).length
      ? submit.error
      : null;

  return (
    <AuthLayout>
      <Link
        to="/login"
        className="-mb-2 flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" />
        Log in
      </Link>
      <AuthHeading
        title="Ask about admission"
        subtitle="Leave your details and the institute will call you back. This doesn't create an account."
      />
      {failure && <FormAlert>{failure.message}</FormAlert>}
      <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-4" noValidate>
        <FormField label="Your name" error={errors.parent_name?.message}>
          {(p) => <Input {...p} {...form.register("parent_name")} autoComplete="name" />}
        </FormField>
        <FormField label="Mobile number" error={errors.phone?.message}>
          {(p) => (
            <Input
              {...p}
              {...form.register("phone")}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
            />
          )}
        </FormField>
        <FormField label="Email (optional)" error={errors.email?.message}>
          {(p) => <Input {...p} {...form.register("email")} type="email" autoComplete="email" />}
        </FormField>
        <FormField label="Student's name" error={errors.student_name?.message}>
          {(p) => <Input {...p} {...form.register("student_name")} autoComplete="off" />}
        </FormField>
        <div className="grid grid-cols-2 gap-3">
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
        </div>
        <FormField label="Message (optional)" error={errors.message?.message}>
          {(p) => (
            <Textarea
              {...p}
              {...form.register("message")}
              rows={3}
              placeholder="Subjects, timings, questions…"
            />
          )}
        </FormField>
        {/* Honeypot: invisible to people and screen readers; bots that fill it are ignored. */}
        <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
          <label>
            Website
            <input tabIndex={-1} autoComplete="off" {...form.register("website")} />
          </label>
        </div>
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Sending…" : "Send"}
        </Button>
      </form>
    </AuthLayout>
  );
}
