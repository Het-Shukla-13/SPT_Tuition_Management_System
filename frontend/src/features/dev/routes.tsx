/**
 * DEVELOPMENT-ONLY preview pages (not included in production builds):
 *   /dev/ui      every shared component, with sample data
 *   /dev/staff   the staff layout (as an admin), no login needed
 *   /dev/portal  the parent portal layout, no login needed
 */
import { Link, Route, Routes } from "react-router";

import { PortalShell } from "@/app/layouts/PortalShell";
import { StaffShell } from "@/app/layouts/StaffShell";
import { CurrentUserContext } from "@/features/auth/session";
import type { User } from "@/lib/api/types";

import { UiKitPage } from "./UiKitPage";

const SAMPLE_ADMIN = {
  id: 1,
  first_name: "Office",
  last_name: "Admin",
  email: "admin@example.com",
  phone: null,
  role: "ADMIN",
  email_verified_at: null,
  phone_verified_at: null,
  google_linked: false,
  created_at: "2026-06-01T10:00:00+05:30",
} as unknown as User;

const SAMPLE_PARENT = {
  ...SAMPLE_ADMIN,
  id: 2,
  first_name: "Kavita",
  last_name: "Shah",
  role: "PORTAL",
} as User;

function DevIndex() {
  return (
    <main className="mx-auto flex max-w-md flex-col gap-3 p-8">
      <h1 className="text-2xl font-extrabold">Dev previews</h1>
      <Link className="font-bold text-primary" to="/dev/ui">
        Component kit
      </Link>
      <Link className="font-bold text-primary" to="/dev/staff">
        Staff layout
      </Link>
      <Link className="font-bold text-primary" to="/dev/portal">
        Portal layout
      </Link>
    </main>
  );
}

export function DevRoutes() {
  return (
    <Routes>
      <Route index element={<DevIndex />} />
      <Route
        path="ui"
        element={
          <div className="mx-auto max-w-[1280px] p-6 sm:p-9">
            <UiKitPage />
          </div>
        }
      />
      <Route
        path="staff/*"
        element={
          <CurrentUserContext.Provider value={SAMPLE_ADMIN}>
            <StaffShell />
          </CurrentUserContext.Provider>
        }
      >
        <Route path="*" element={<UiKitPage />} />
      </Route>
      <Route
        path="portal/*"
        element={
          <CurrentUserContext.Provider value={SAMPLE_PARENT}>
            <PortalShell />
          </CurrentUserContext.Provider>
        }
      >
        <Route path="*" element={<PortalSample />} />
      </Route>
    </Routes>
  );
}

function PortalSample() {
  return (
    <div className="flex flex-col">
      <header className="flex flex-col gap-4 rounded-b-3xl bg-board px-5 pt-5 pb-7 text-white">
        <span className="text-sm text-board-muted">Std 10 · CBSE</span>
        <h1 className="text-[26px] font-extrabold">Good evening, Kavita</h1>
      </header>
      <div className="flex flex-col gap-3.5 p-4">
        <div className="rounded-[18px] border-2 border-primary bg-surface p-4">
          <p className="text-xs font-extrabold tracking-wider text-muted uppercase">Next test</p>
          <p className="mt-1 text-lg font-bold">Real Numbers: unit test</p>
          <p className="text-sm text-muted">Maths · Wed 11 Nov, 4:00 pm</p>
        </div>
        <p className="text-sm text-muted">
          The real portal screens arrive in F6. The tab bar below is the real one.
        </p>
      </div>
    </div>
  );
}
