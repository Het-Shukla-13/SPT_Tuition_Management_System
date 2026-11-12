import { FileTextIcon, UploadIcon } from "lucide-react";
import { useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

const MB = 1024 * 1024;

/**
 * Pick a file by tapping or dropping it. Checks type and size in the browser
 * for a quick, friendly message; the server checks again (real PDF, size).
 */
export function FileInput({
  label,
  value,
  onChange,
  accept = "application/pdf",
  maxMb = 20,
  error,
  hint = "PDF only, up to 20 MB",
}: {
  label: string;
  value: File | null;
  onChange: (file: File | null) => void;
  accept?: string;
  maxMb?: number;
  error?: string;
  hint?: string;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (file: File | undefined) => {
    if (!file) return;
    const accepted = accept.split(",").map((a) => a.trim());
    if (
      !accepted.includes(file.type) &&
      !accepted.some((a) => file.name.toLowerCase().endsWith(a.replace("application/", ".")))
    ) {
      setLocalError(`${file.name} isn't a PDF. Save it as PDF and try again.`);
      return;
    }
    if (file.size > maxMb * MB) {
      setLocalError(`${file.name} is larger than ${maxMb} MB.`);
      return;
    }
    setLocalError(null);
    onChange(file);
  };

  const shown = localError ?? error;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-bold">
        {label}
      </label>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex flex-col items-center gap-1.5 rounded-[var(--radius-card)] border-2 border-dashed px-4 py-5 text-center",
          value ? "border-solid border-primary bg-primary-tint" : "border-line-strong bg-subtle",
          dragging && "border-primary",
          shown && "border-danger",
        )}
      >
        {value ? (
          <>
            <FileTextIcon className="size-6 text-primary" aria-hidden="true" />
            <b className="max-w-full truncate">{value.name}</b>
            <span className="text-[13px] text-muted">{(value.size / MB).toFixed(1)} MB</span>
            <span className="flex gap-3 text-[13px] font-bold">
              <button
                type="button"
                className="min-h-9 text-primary"
                onClick={() => input.current?.click()}
              >
                Change file
              </button>
              <button type="button" className="min-h-9 text-danger" onClick={() => onChange(null)}>
                Remove
              </button>
            </span>
          </>
        ) : (
          <>
            <UploadIcon className="size-6 text-muted" aria-hidden="true" />
            <button
              type="button"
              className="min-h-9 font-bold text-primary"
              onClick={() => input.current?.click()}
            >
              Choose a file
            </button>
            <span className="text-[13px] text-muted">or drop it here · {hint}</span>
          </>
        )}
        <input
          ref={input}
          id={id}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      {shown && (
        <span role="alert" className="text-[13px] text-danger">
          {shown}
        </span>
      )}
    </div>
  );
}
