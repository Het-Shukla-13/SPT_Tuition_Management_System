import type { ReactNode } from "react";

import { INSTITUTE_NAME, LogoMark } from "@/components/shared/Logo";

/**
 * Login-type screens: the chalkboard brand panel beside the form on desktop;
 * on phones the panel shrinks to a header so the form is above the keyboard.
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-ground lg:flex-row">
      <aside className="flex flex-col justify-between gap-8 bg-board px-6 py-6 text-board-text lg:min-h-dvh lg:flex-1 lg:px-14 lg:py-14">
        <div className="flex items-center gap-3">
          <LogoMark className="size-11" />
          <span className="text-[22px] font-extrabold text-white">Chalkboard</span>
        </div>
        <div className="hidden max-w-[520px] flex-col gap-4 lg:flex">
          <span className="text-sm font-bold tracking-wider text-chalk uppercase">
            {INSTITUTE_NAME}
          </span>
          <p className="text-[44px] leading-[1.1] font-extrabold tracking-tight text-white">
            Tests, notes, marks and fees, all in one place.
          </p>
          <p className="text-base leading-relaxed text-board-text/80">
            For students, parents and teachers of the institute. Your login was created by the
            institute: use the email you gave at admission.
          </p>
        </div>
        <span className="hidden text-[13px] text-board-muted lg:block">
          Need help? Contact the institute office.
        </span>
      </aside>
      <main className="flex flex-1 items-start justify-center px-4 py-8 sm:items-center sm:py-12">
        <div className="flex w-full max-w-[420px] flex-col gap-5 rounded-[18px] border border-line bg-surface p-6 sm:p-9">
          {children}
        </div>
      </main>
    </div>
  );
}

export function AuthHeading({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h1 className="text-[26px] font-extrabold tracking-tight">{title}</h1>
      {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
    </div>
  );
}

/** Error/notice box above a form. */
export function FormAlert({
  tone = "danger",
  children,
}: {
  tone?: "danger" | "info";
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={
        tone === "danger"
          ? "rounded-[var(--radius-control)] bg-danger-bg px-4 py-3 text-sm text-danger"
          : "rounded-[var(--radius-control)] bg-info-bg px-4 py-3 text-sm text-info"
      }
    >
      {children}
    </div>
  );
}
