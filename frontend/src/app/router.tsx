import { createBrowserRouter, type RouteObject } from "react-router";

import { ComingSoon } from "@/components/shared/ComingSoon";
import { AcademicsPage } from "@/features/academics/pages/AcademicsPage";
import { AccountPage } from "@/features/auth/pages/AccountPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";
import { LearningDetailPage } from "@/features/learning/pages/LearningDetailPage";
import { LearningListPage } from "@/features/learning/pages/LearningListPage";
import { UploadPage } from "@/features/learning/pages/UploadPage";
import { AdmissionPage } from "@/features/students/pages/AdmissionPage";
import { StudentDetailPage } from "@/features/students/pages/StudentDetailPage";
import { StudentsPage } from "@/features/students/pages/StudentsPage";
import { UserDetailPage } from "@/features/users/pages/UserDetailPage";
import { UsersPage } from "@/features/users/pages/UsersPage";

import { HomeRedirect, NotFound, RequireAuth } from "./guards";
import { PortalShell } from "./layouts/PortalShell";
import { StaffShell } from "./layouts/StaffShell";

/**
 * Every URL of the app. Pages not built yet show <ComingSoon>, so the menus
 * and role guards already work end to end.
 */
const staffRoutes: RouteObject[] = [
  { index: true, element: <ComingSoon title="Dashboard" step="F7" /> },
  ...(["tests", "notes"] as const).flatMap((kind): RouteObject[] => [
    { path: kind, element: <LearningListPage key={kind} kind={kind} /> },
    { path: `${kind}/new`, element: <UploadPage key={kind} kind={kind} /> },
    { path: `${kind}/:id`, element: <LearningDetailPage key={kind} kind={kind} /> },
  ]),
  { path: "account", element: <AccountPage /> },
];

const adminOnlyRoutes: RouteObject[] = [
  { path: "students", element: <StudentsPage /> },
  { path: "students/new", element: <AdmissionPage /> },
  { path: "students/:id", element: <StudentDetailPage /> },
  { path: "fees", element: <ComingSoon title="Fees" step="F5" /> },
  { path: "enquiries", element: <ComingSoon title="Enquiries" step="F7" /> },
  { path: "users", element: <UsersPage /> },
  { path: "users/:id", element: <UserDetailPage /> },
  { path: "academics", element: <AcademicsPage /> },
];

const portalRoutes: RouteObject[] = [
  { index: true, element: <ComingSoon title="Home" step="F6" /> },
  { path: "tests", element: <ComingSoon title="Tests" step="F6" /> },
  { path: "notes", element: <ComingSoon title="Notes" step="F6" /> },
  { path: "fees", element: <ComingSoon title="Fees" step="F6" /> },
  { path: "account", element: <AccountPage /> },
];

export const routes: RouteObject[] = [
  { path: "/", element: <HomeRedirect /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
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
