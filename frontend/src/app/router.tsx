import { createBrowserRouter, Outlet, type RouteObject } from "react-router";

import { AcademicsPage } from "@/features/academics/pages/AcademicsPage";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { EnquiriesPage } from "@/features/enquiries/pages/EnquiriesPage";
import { EnquiryDetailPage } from "@/features/enquiries/pages/EnquiryDetailPage";
import { PublicEnquiryPage } from "@/features/enquiries/pages/PublicEnquiryPage";
import { AccountPage } from "@/features/auth/pages/AccountPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";
import { FeeAccountPage } from "@/features/fees/pages/FeeAccountPage";
import { FeesPage } from "@/features/fees/pages/FeesPage";
import { StudentGate } from "@/features/portal/components/StudentGate";
import { PortalFeesPage } from "@/features/portal/pages/PortalFeesPage";
import { PortalHomePage } from "@/features/portal/pages/PortalHomePage";
import { PortalNotesPage } from "@/features/portal/pages/PortalNotesPage";
import { PortalTestDetailPage } from "@/features/portal/pages/PortalTestDetailPage";
import { PortalTestsPage } from "@/features/portal/pages/PortalTestsPage";
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
 * Every URL of the app. Which roles reach each group is decided by the guards
 * below, matching the menus in navigation.ts.
 */
const staffRoutes: RouteObject[] = [
  { index: true, element: <DashboardPage /> },
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
  { path: "fees", element: <FeesPage /> },
  { path: "fees/accounts/:id", element: <FeeAccountPage /> },
  { path: "enquiries", element: <EnquiriesPage /> },
  { path: "enquiries/:id", element: <EnquiryDetailPage /> },
  { path: "users", element: <UsersPage /> },
  { path: "users/:id", element: <UserDetailPage /> },
  { path: "academics", element: <AcademicsPage /> },
];

const portalRoutes: RouteObject[] = [
  {
    // Everything about a student; the account page works even with no student linked.
    element: (
      <StudentGate>
        <Outlet />
      </StudentGate>
    ),
    children: [
      { index: true, element: <PortalHomePage /> },
      { path: "tests", element: <PortalTestsPage /> },
      { path: "tests/:id", element: <PortalTestDetailPage /> },
      { path: "notes", element: <PortalNotesPage /> },
      { path: "fees", element: <PortalFeesPage /> },
    ],
  },
  { path: "account", element: <AccountPage /> },
];

export const routes: RouteObject[] = [
  { path: "/", element: <HomeRedirect /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/enquire", element: <PublicEnquiryPage /> },
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
