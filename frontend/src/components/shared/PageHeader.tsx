import { ArrowLeftIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { useDocumentTitle } from "@/lib/useDocumentTitle";

/** Title row of every page: optional back link, eyebrow text and actions. */
export function PageHeader({
  title,
  eyebrow,
  back,
  actions,
}: {
  title: string;
  eyebrow?: ReactNode;
  back?: { to: string; label: string };
  actions?: ReactNode;
}) {
  useDocumentTitle(title);
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
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          {eyebrow && <span className="text-sm text-muted">{eyebrow}</span>}
          <h1 className="text-[28px] leading-tight font-extrabold tracking-tight sm:text-[30px]">
            {title}
          </h1>
        </div>
        {actions && <div className="flex flex-wrap gap-2.5">{actions}</div>}
      </div>
    </div>
  );
}
