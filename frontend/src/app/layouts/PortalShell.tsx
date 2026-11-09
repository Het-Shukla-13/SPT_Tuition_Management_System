import { NavLink, Outlet } from "react-router";

import { PORTAL_NAV } from "@/app/navigation";
import { cn } from "@/lib/utils";

/**
 * Parent & student layout: phone-first. A single column (centred on bigger
 * screens) with a bottom tab bar that stays in thumb reach.
 */
export function PortalShell() {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[520px] flex-col bg-ground sm:border-x sm:border-line">
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
