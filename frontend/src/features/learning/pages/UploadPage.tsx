import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactNode, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { FileInput } from "@/components/shared/FileInput";
import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { ReferenceSelect } from "@/features/academics";
import { ApiError } from "@/lib/api/envelope";

import { type Kind, SEMESTER_OPTIONS, useCreateItem } from "../api";
import { ChapterPicker } from "../components/ChapterPicker";
import { KIND_TEXT } from "../text";

const schema = z.object({
  title: z.string().trim().min(1, "Give it a title."),
  description: z.string(),
  board: z.string().min(1, "Choose a board."),
  standard: z.string().min(1, "Choose a standard."),
  subject: z.string().min(1, "Choose a subject."),
  chapters: z.array(z.number()),
  semester: z.string(),
  school: z.string(),
  test_date: z.string(),
  max_marks: z.string().regex(/^(\d+(\.\d{1,2})?)?$/, "Enter a number, e.g. 25."),
  duration_minutes: z.string().regex(/^\d*$/, "Enter minutes, e.g. 60."),
  file: z.instanceof(File, { message: "Choose the PDF." }),
  answer_key: z.instanceof(File).nullable(),
});
type Values = z.infer<typeof schema>;

/** Upload a test (paper + optional answer key) or notes, then go assign it. */
export function UploadPage({ kind }: { kind: Kind }) {
  const text = KIND_TEXT[kind];
  const navigate = useNavigate();
  const create = useCreateItem(kind);
  const [duplicate, setDuplicate] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      description: "",
      board: "",
      standard: "",
      subject: "",
      chapters: [],
      semester: "",
      school: "",
      test_date: "",
      max_marks: "",
      duration_minutes: "60",
      file: undefined as unknown as File,
      answer_key: null,
    },
  });
  const errors = form.formState.errors;
  const [board, standard, subject] = useWatch({
    control: form.control,
    name: ["board", "standard", "subject"],
  });

  const submit = async (values: Values, confirmDuplicate = false) => {
    const body: Record<string, unknown> = {
      title: values.title.trim(),
      description: values.description.trim(),
      board: values.board,
      standard: values.standard,
      subject: values.subject,
      chapters: values.chapters,
      semester: values.semester,
      file: values.file,
      confirm_duplicate: confirmDuplicate ? "true" : undefined,
    };
    if (kind === "tests") {
      Object.assign(body, {
        school: values.school,
        test_date: values.test_date,
        max_marks: values.max_marks,
        duration_minutes: values.duration_minutes,
        answer_key: values.answer_key ?? undefined,
      });
    }
    try {
      const item = await create.mutateAsync(body);
      toast.success(`Uploaded. Now choose who gets it.`);
      navigate(`/staff/${kind}/${item.id}?assign=1`);
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      if (err.code === "DUPLICATE_DOCUMENT") {
        setDuplicate(true);
        return;
      }
      let shown = false;
      for (const [field, messages] of Object.entries(err.fieldErrors)) {
        if (field in schema.shape) {
          form.setError(field as keyof Values, { message: messages.join(" ") });
          shown = true;
        }
      }
      if (!shown) toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        back={{ to: `/staff/${kind}`, label: text.title }}
        title={`Upload ${text.singular}`}
      />
      {duplicate && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] bg-warning-bg p-4 text-warning"
        >
          <span>
            <b>This exact PDF is already uploaded.</b> Upload it again anyway?
          </span>
          <span className="flex gap-2">
            <Button
              size="sm"
              className="bg-warning text-white"
              onClick={form.handleSubmit((v) => submit(v, true))}
            >
              Upload anyway
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setDuplicate(false)}>
              Cancel
            </Button>
          </span>
        </div>
      )}
      <form
        onSubmit={form.handleSubmit((v) => submit(v))}
        className="flex max-w-[980px] flex-col gap-5"
        noValidate
      >
        <Card className="gap-4 p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">Files</h2>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))] gap-4">
            <Controller
              control={form.control}
              name="file"
              render={({ field }) => (
                <FileInput
                  label={kind === "tests" ? "Question paper (required)" : "Notes PDF (required)"}
                  value={field.value ?? null}
                  onChange={(f) => field.onChange(f ?? undefined)}
                  error={errors.file?.message}
                />
              )}
            />
            {kind === "tests" && (
              <Controller
                control={form.control}
                name="answer_key"
                render={({ field }) => (
                  <FileInput
                    label="Answer key (optional, can add later)"
                    value={field.value}
                    onChange={field.onChange}
                    hint="PDF · students see it only after the test ends"
                  />
                )}
              />
            )}
          </div>
        </Card>

        <Card className="gap-4 p-5 sm:p-6">
          <h2 className="text-lg font-extrabold">
            About the {kind === "tests" ? "test" : "notes"}
          </h2>
          <FormField label="Title" error={errors.title?.message}>
            {(p) => (
              <Input
                {...p}
                {...form.register("title")}
                placeholder={
                  kind === "tests" ? "e.g. Real Numbers: unit test" : "e.g. Real numbers: summary"
                }
              />
            )}
          </FormField>
          <Grid>
            <FormField label="Board" error={errors.board?.message}>
              {(p) => <ReferenceSelect {...p} {...form.register("board")} resource="boards" />}
            </FormField>
            <FormField label="Standard" error={errors.standard?.message}>
              {(p) => (
                <ReferenceSelect {...p} {...form.register("standard")} resource="standards" />
              )}
            </FormField>
            <FormField label="Subject" error={errors.subject?.message}>
              {(p) => <ReferenceSelect {...p} {...form.register("subject")} resource="subjects" />}
            </FormField>
            <FormField label="Semester (optional)">
              {(p) => (
                <NativeSelect {...p} {...form.register("semester")}>
                  <option value="">Not set</option>
                  {SEMESTER_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            {kind === "tests" && (
              <>
                <FormField label="Max marks" error={errors.max_marks?.message}>
                  {(p) => (
                    <Input
                      {...p}
                      {...form.register("max_marks")}
                      inputMode="decimal"
                      placeholder="e.g. 25"
                    />
                  )}
                </FormField>
                <FormField
                  label="Duration (minutes)"
                  hint="The answer key unlocks after start + duration."
                  error={errors.duration_minutes?.message}
                >
                  {(p) => (
                    <Input {...p} {...form.register("duration_minutes")} inputMode="numeric" />
                  )}
                </FormField>
                <FormField label="Planned date (optional)">
                  {(p) => <Input {...p} {...form.register("test_date")} type="date" />}
                </FormField>
                <FormField label="Only for one school? (optional)">
                  {(p) => (
                    <ReferenceSelect
                      {...p}
                      {...form.register("school")}
                      resource="schools"
                      placeholder="All schools"
                    />
                  )}
                </FormField>
              </>
            )}
          </Grid>
          <Controller
            control={form.control}
            name="chapters"
            render={({ field }) => (
              <ChapterPicker
                board={board}
                standard={standard}
                subject={subject}
                value={field.value}
                onChange={field.onChange}
                error={errors.chapters?.message}
              />
            )}
          />
          <FormField label="Description (optional)">
            {(p) => <Textarea {...p} {...form.register("description")} rows={2} />}
          </FormField>
        </Card>

        <div className="flex justify-end gap-2.5">
          <Button asChild variant="secondary">
            <Link to={`/staff/${kind}`}>Cancel</Link>
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </form>
    </>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,200px),1fr))] gap-4">
      {children}
    </div>
  );
}
