import { ArrowLeftIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { LogoMark } from "@/components/shared/Logo";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

/** A readable single-column page for the Privacy Policy and Terms (no login needed). */
export function LegalLayout({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  useDocumentTitle(title);
  return (
    <div className="min-h-dvh bg-ground">
      <header className="flex h-14 items-center gap-2.5 bg-board px-4 text-white sm:px-8">
        <LogoMark className="size-8" />
        <span className="text-base font-extrabold">Chalkboard</span>
      </header>
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:px-8">
        <Link
          to="/login"
          className="flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
        >
          <ArrowLeftIcon className="size-4" aria-hidden="true" /> Back to log in
        </Link>
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
          <p className="text-sm text-muted">Sai Personal Tuitions · Last updated {updated}</p>
        </div>
        <article className="flex flex-col gap-6 rounded-[var(--radius-card)] border border-line bg-surface p-5 text-[15px] leading-relaxed sm:p-8 [&_h2]:text-lg [&_h2]:font-extrabold [&_li]:ml-5 [&_li]:list-disc [&_section]:flex [&_section]:flex-col [&_section]:gap-2 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1">
          {children}
        </article>
      </main>
    </div>
  );
}
