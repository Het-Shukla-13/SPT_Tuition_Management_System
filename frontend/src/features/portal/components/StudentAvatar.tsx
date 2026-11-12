import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

import { useStudentPhotoUrl } from "../api";

/** The student's photo, or their initials when there is none. */
export function StudentAvatar({
  student,
  className,
}: {
  student: { id: number; first_name: string; last_name: string; has_photo: boolean };
  className?: string;
}) {
  const photo = useStudentPhotoUrl(student.id, student.has_photo);
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary-tint font-extrabold text-primary",
        className,
      )}
    >
      {photo.data ? (
        <img src={photo.data} alt="" className="size-full object-cover" />
      ) : (
        initials(`${student.first_name} ${student.last_name}`)
      )}
    </span>
  );
}
