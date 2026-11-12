import { CameraIcon } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/envelope";
import type { StudentDetail } from "@/lib/api/types";
import { initials } from "@/lib/format";

import { studentName, useStudentPhoto, useStudentPhotoMutations } from "../api";

const MAX_MB = 5;

/**
 * The student's photo (or initials) with upload / replace / remove. The
 * server re-encodes every photo and strips its metadata (e.g. GPS location).
 */
export function StudentPhoto({ student }: { student: StudentDetail }) {
  const photo = useStudentPhoto(student.id, student.has_photo);
  const { upload, remove } = useStudentPhotoMutations(student.id);
  const input = useRef<HTMLInputElement>(null);

  const onFile = (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`The photo is too large (max ${MAX_MB} MB).`);
      return;
    }
    upload.mutate(file, {
      onSuccess: () => toast.success("Photo saved."),
      onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't upload the photo."),
    });
  };

  return (
    <div className="flex items-center gap-4">
      <div className="relative size-[72px] shrink-0 overflow-hidden rounded-2xl bg-primary-tint">
        {student.has_photo && photo.data ? (
          <img
            src={photo.data}
            alt={`Photo of ${studentName(student)}`}
            className="size-full object-cover"
          />
        ) : (
          <span
            className="flex size-full items-center justify-center text-[26px] font-extrabold text-primary"
            aria-hidden="true"
          >
            {initials(studentName(student))}
          </span>
        )}
      </div>
      <div className="flex flex-col items-start gap-1">
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          aria-label="Choose a photo"
          onChange={(e) => {
            onFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button
          variant="ghost"
          size="sm"
          disabled={upload.isPending}
          onClick={() => input.current?.click()}
        >
          <CameraIcon aria-hidden="true" />{" "}
          {upload.isPending ? "Uploading…" : student.has_photo ? "Replace photo" : "Add photo"}
        </Button>
        {student.has_photo && (
          <Button
            variant="ghost"
            size="sm"
            className="text-danger"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(undefined, { onSuccess: () => toast.success("Photo removed.") })
            }
          >
            Remove photo
          </Button>
        )}
      </div>
    </div>
  );
}
