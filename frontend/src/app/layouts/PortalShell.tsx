import { Link, NavLink, Outlet } from "react-router";

import { LogoMark } from "@/components/shared/Logo";
import { useCurrentUser } from "@/features/auth/session";
import { initials } from "@/lib/format";

import { PORTAL_NAV } from "@/app/navigation";
import { cn } from "@/lib/utils";

/**
 * Parent & student layout: phone-first. A single column (centred on bigger
 * screens) with a bottom tab bar that stays in thumb reach.
 */
export function PortalShell() {
  const user = useCurrentUser();
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[520px] flex-col bg-ground sm:border-x sm:border-line">
      <header className="flex h-14 items-center justify-between bg-board px-4">
        <Link
          to="/portal"
          className="flex items-center gap-2.5 text-white"
          aria-label="Chalkboard home"
        >
          <LogoMark className="size-8" />
          <span className="text-base font-extrabold">Chalkboard</span>
        </Link>
        <Link
          to="/portal/account"
          aria-label="My account"
          className="flex size-11 items-center justify-center rounded-full bg-board-hover text-sm font-extrabold text-white"
        >
          {initials(`${user.first_name} ${user.last_name}`)}
        </Link>
      </header>
      <div className="flex flex-1 flex-col pb-24">
        <Outlet />
      </div>
      <nav
        aria-label="Portal"
        className="fixed inset-x-0 bottom-0 z-30 mx-auto grid max-w-[520px] grid-cols-4 border-t border-line bg-surface px-2 pt-2 pb-[max(12px,env(safe-area-inset-bottom))]"
      >
        {PORTAL_NAV.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={"end" in tab ? tab.end : false}
            className={({ isActive }) =>
              cn(
                "flex min-h-14 flex-col items-center justify-center gap-1 text-xs",
                isActive ? "font-extrabold text-primary" : "font-semibold text-muted",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    "flex h-7 w-13 items-center justify-center rounded-full",
                    isActive && "bg-primary-tint",
                  )}
                >
                  <tab.icon className="size-5" aria-hidden="true" />
                </span>
                {tab.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
