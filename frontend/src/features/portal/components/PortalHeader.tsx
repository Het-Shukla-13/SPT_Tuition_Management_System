import { ArrowLeftIcon } from "lucide-react";
import { Link } from "react-router";

import { useDocumentTitle } from "@/lib/useDocumentTitle";

import { studentName, useActiveStudent } from "../student";
import { StudentAvatar } from "./StudentAvatar";

/** Page title, with whose data this is and (for parents of several children) a switch. */
export function PortalHeader({
  title,
  back,
}: {
  title: string;
  back?: { to: string; label: string };
}) {
  const { student, students, choose } = useActiveStudent();
  useDocumentTitle(students.length > 1 ? `${title} – ${student.first_name}` : title);
  return (
    <div className="flex flex-col gap-3">
      {back && (
        <Link
          to={back.to}
          className="flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
        >
          <ArrowLeftIcon className="size-4" aria-hidden="true" />
          {back.label}
        </Link>
      )}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold">{title}</h1>
        {students.length > 1 && (
          <button
            type="button"
            onClick={choose}
            aria-label={`Showing ${studentName(student)}. Switch student`}
            className="flex min-h-11 items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1 text-sm font-bold"
          >
            <StudentAvatar student={student} className="size-8 text-xs" />
            {student.first_name}
            <span className="text-primary">Switch</span>
          </button>
        )}
      </div>
    </div>
  );
}
