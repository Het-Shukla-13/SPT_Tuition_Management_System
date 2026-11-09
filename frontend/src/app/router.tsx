import { createBrowserRouter, type RouteObject } from "react-router";

import { ComingSoon } from "@/components/shared/ComingSoon";

import { HomeRedirect, NotFound, RequireAuth } from "./guards";
import { PortalShell } from "./layouts/PortalShell";
import { StaffShell } from "./layouts/StaffShell";
import { LoginPlaceholder } from "./LoginPlaceholder";

/**
 * Every URL of the app. Pages not built yet show <ComingSoon>, so the menus
 * and role guards already work end to end.
 */
const staffRoutes: RouteObject[] = [
  { index: true, element: <ComingSoon title="Dashboard" step="F7" /> },
  { path: "tests", element: <ComingSoon title="Tests" step="F4" /> },
  { path: "notes", element: <ComingSoon title="Notes" step="F4" /> },
];

const adminOnlyRoutes: RouteObject[] = [
  { path: "students", element: <ComingSoon title="Students" step="F3" /> },
  { path: "fees", element: <ComingSoon title="Fees" step="F5" /> },
  { path: "enquiries", element: <ComingSoon title="Enquiries" step="F7" /> },
  { path: "users", element: <ComingSoon title="Users & invites" step="F2" /> },
  { path: "academics", element: <ComingSoon title="Academics setup" step="F2" /> },
];

const portalRoutes: RouteObject[] = [
  { index: true, element: <ComingSoon title="Home" step="F6" /> },
  { path: "tests", element: <ComingSoon title="Tests" step="F6" /> },
  { path: "notes", element: <ComingSoon title="Notes" step="F6" /> },
  { path: "fees", element: <ComingSoon title="Fees" step="F6" /> },
];

export const routes: RouteObject[] = [
  { path: "/", element: <HomeRedirect /> },
  { path: "/login", element: <LoginPlaceholder /> },
  {
    path: "/staff",
    element: <RequireAuth roles={["ADMIN", "TEACHER"]} />,
    children: [
      {
        element: <StaffShell />,
        children: [
          ...staffRoutes,
          { element: <RequireAuth roles={["ADMIN"]} />, children: adminOnlyRoutes },
        ],
      },
    ],
  },
  {
    path: "/portal",
    element: <RequireAuth roles={["PORTAL"]} />,
    children: [{ element: <PortalShell />, children: portalRoutes }],
  },
  ...(import.meta.env.DEV
    ? [
        {
          path: "/dev/*",
          lazy: () => import("@/features/dev/routes").then((m) => ({ Component: m.DevRoutes })),
        },
      ]
    : []),
  { path: "*", element: <NotFound /> },
];

export const router = createBrowserRouter(routes);
