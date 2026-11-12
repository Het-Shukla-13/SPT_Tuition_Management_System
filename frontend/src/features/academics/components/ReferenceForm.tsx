import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { ApiError } from "@/lib/api/envelope";
import { cn } from "@/lib/utils";

import { type ReferenceItem, useReferenceOptions, useSaveReference } from "../api";
import type { FieldConfig, ReferenceConfig } from "../config";

type Values = Record<string, string | boolean>;

function initialValues(config: ReferenceConfig, item: ReferenceItem | null): Values {
  return Object.fromEntries(
    config.fields.map((f) => {
      const raw = item?.[f.name];
      if (f.type === "checkbox") return [f.name, Boolean(raw)];
      return [f.name, raw === null || raw === undefined ? "" : String(raw)];
    }),
  );
}

/** Add / edit dialog for any reference type, built from its field config. */
export function ReferenceForm({
  config,
  item,
  open,
  onOpenChange,
}: {
  config: ReferenceConfig;
  item: ReferenceItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const save = useSaveReference(config.key);
  const [values, setValues] = useState<Values>(() => initialValues(config, item));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const editing = item !== null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const missing = Object.fromEntries(
      config.fields
        .filter((f) => f.required && f.type !== "checkbox" && !String(values[f.name] ?? "").trim())
        .map((f) => [f.name, `Enter ${f.label.toLowerCase()}.`]),
    );
    setErrors(missing);
    if (Object.keys(missing).length) return;

    const body: Record<string, unknown> = {};
    for (const field of config.fields) {
      if (editing && field.createOnly) continue;
      const value = values[field.name];
      if (field.type === "checkbox") body[field.name] = Boolean(value);
      else if (field.type === "number" || field.type === "select")
        body[field.name] = value === "" ? null : Number(value);
      else body[field.name] = String(value).trim();
    }
    try {
      await save.mutateAsync({ id: item?.id, body });
      toast.success(editing ? "Saved." : `${capitalise(config.singular)} added.`);
      onOpenChange(false);
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      const fieldErrors = Object.fromEntries(
        Object.entries(err.fieldErrors).map(([k, v]) => [k, v.join(" ")]),
      );
      setErrors(fieldErrors);
      if (!Object.keys(fieldErrors).some((k) => config.fields.some((f) => f.name === k)))
        toast.error(err.message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !save.isPending && onOpenChange(next)}>
      <DialogContent title={editing ? `Edit ${config.singular}` : `Add ${config.singular}`}>
        <form onSubmit={submit} className="grid grid-cols-2 gap-4" noValidate>
          {config.fields.map((field) => (
            <div
              key={field.name}
              className={cn(field.width === "half" ? "col-span-2 sm:col-span-1" : "col-span-2")}
            >
              <Field
                field={field}
                value={values[field.name]!}
                error={errors[field.name]}
                disabled={editing && field.createOnly}
                onChange={(v) => setValues((prev) => ({ ...prev, [field.name]: v }))}
              />
            </div>
          ))}
          <div className="col-span-2 flex justify-end gap-2.5 pt-1">
            <DialogClose asChild>
              <Button variant="secondary" disabled={save.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : editing ? "Save" : "Add"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  field,
  value,
  error,
  disabled,
  onChange,
}: {
  field: FieldConfig;
  value: string | boolean;
  error?: string;
  disabled?: boolean;
  onChange: (value: string | boolean) => void;
}) {
  if (field.type === "checkbox") {
    return (
      <label className="flex min-h-11 items-start gap-3 text-sm font-semibold">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          className="mt-0.5 size-5 accent-[var(--color-primary)]"
        />
        {field.label}
        {error && <span className="block text-[13px] text-danger">{error}</span>}
      </label>
    );
  }
  return (
    <FormField
      label={field.label}
      hint={disabled ? "Can't be changed after it's created." : field.hint}
      error={error}
    >
      {(p) =>
        field.type === "select" ? (
          <OptionsSelect
            {...p}
            field={field}
            value={String(value)}
            onChange={onChange}
            disabled={disabled}
          />
        ) : (
          <Input
            {...p}
            type={field.type}
            inputMode={field.type === "number" ? "numeric" : undefined}
            value={String(value)}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
          />
        )
      }
    </FormField>
  );
}

function OptionsSelect({
  field,
  value,
  onChange,
  disabled,
  ...aria
}: {
  field: FieldConfig;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  id: string;
}) {
  const options = useReferenceOptions(field.optionsFrom!);
  return (
    <NativeSelect
      {...aria}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || options.isPending}
    >
      <option value="">{field.required ? "Choose…" : "None"}</option>
      {options.data?.map((o) => (
        <option key={o.id} value={o.id}>
          {field.optionLabel ? field.optionLabel(o) : String(o.name ?? o.id)}
        </option>
      ))}
    </NativeSelect>
  );
}

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
