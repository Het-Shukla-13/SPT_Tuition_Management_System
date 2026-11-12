import { LogOutIcon, MenuIcon } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { staffNavFor } from "@/app/navigation";
import { Logo } from "@/components/shared/Logo";
import { NavigationProgress, SkipLink } from "@/components/shared/PageChrome";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { displayName, ROLE_LABEL, useCurrentUser, useLogout } from "@/features/auth/session";
import type { User } from "@/lib/api/types";
import { initials } from "@/lib/format";
import { MAIN_ID, useFocusMainOnNavigate } from "@/lib/useFocusMainOnNavigate";
import { cn } from "@/lib/utils";

/**
 * Admin & teacher layout: sidebar on desktop, a top bar + slide-in menu on
 * phones. Pages render in <Outlet />.
 */
export function StaffShell() {
  const user = useCurrentUser();
  const [menuOpen, setMenuOpen] = useState(false);
  const mainRef = useFocusMainOnNavigate<HTMLElement>();

  return (
    <div className="flex min-h-dvh">
      <SkipLink />
      <NavigationProgress />
      <aside className="sticky top-0 hidden h-dvh w-[248px] shrink-0 lg:block">
        <Sidebar user={user} />
      </aside>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent title="Menu" side="left">
          <Sidebar user={user} onNavigate={() => setMenuOpen(false)} />
        </DialogContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-board-line bg-board px-2 lg:hidden">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMenuOpen(true)}
            className="flex size-11 items-center justify-center rounded-lg text-white hover:bg-board-hover"
          >
            <MenuIcon className="size-6" />
          </button>
          <Logo subtitle={false} />
        </header>
        <main
          id={MAIN_ID}
          ref={mainRef}
          tabIndex={-1}
          className="mx-auto flex w-full max-w-[1280px] min-w-0 flex-col gap-6 px-4 py-6 outline-none sm:px-9 sm:py-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Sidebar({ user, onNavigate }: { user: User; onNavigate?: () => void }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const name = displayName(user);

  return (
    <nav
      aria-label="Main"
      className="flex h-full flex-col gap-6 overflow-y-auto bg-board px-3.5 py-5 text-board-text"
    >
      <div className="px-2">
        <Logo />
      </div>
      <ul className="flex flex-1 flex-col gap-1">
        {staffNavFor(user.role).map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex h-11 items-center gap-3 rounded-[var(--radius-control)] px-3 text-[15px]",
                  isActive
                    ? "bg-primary font-bold text-white"
                    : "font-medium text-board-text/85 hover:bg-board-hover",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn("size-[18px]", isActive ? "text-chalk" : "text-board-muted")}
                    aria-hidden="true"
                  />
                  {item.label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2.5 border-t border-board-line px-2 pt-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-chalk text-sm font-extrabold text-board">
          {initials(name)}
        </span>
        <Link
          to="/staff/account"
          onClick={onNavigate}
          className="flex min-h-11 min-w-0 flex-1 flex-col justify-center rounded-lg hover:underline"
        >
          <span className="truncate text-sm font-bold text-white">{name}</span>
          <span className="text-xs text-board-muted">{ROLE_LABEL[user.role]} · My account</span>
        </Link>
        <button
          type="button"
          aria-label="Log out"
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}
          className="flex size-11 items-center justify-center rounded-lg text-board-muted hover:bg-board-hover hover:text-white"
        >
          <LogOutIcon className="size-5" />
        </button>
      </div>
    </nav>
  );
}
