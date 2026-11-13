import type { ComponentType } from "react";
import { createBrowserRouter, Outlet, type RouteObject, ScrollRestoration } from "react-router";

import { StudentGate } from "@/features/portal/components/StudentGate";

import { FullPageLoader, HomeRedirect, NotFound, RequireAuth } from "./guards";
import { PortalShell } from "./layouts/PortalShell";
import { StaffShell } from "./layouts/StaffShell";
import { RouteError } from "./RouteError";

/**
 * Each page's code is downloaded only when it's first opened, so the app
 * starts fast on a phone; the shells, guards and login stay small.
 */
function page<K extends string>(
  load: () => Promise<Record<K, ComponentType>>,
  name: K,
): Pick<RouteObject, "lazy"> {
  return { lazy: async () => ({ Component: (await load())[name] }) };
}

const learning = () => import("@/features/learning/pages/LearningListPage");
const upload = () => import("@/features/learning/pages/UploadPage");
const learningDetail = () => import("@/features/learning/pages/LearningDetailPage");

/**
 * Every URL of the app. Which roles reach each group is decided by the guards
 * below, matching the menus in navigation.ts.
 */
const staffRoutes: RouteObject[] = [
  {
    index: true,
    ...page(() => import("@/features/dashboard/pages/DashboardPage"), "DashboardPage"),
  },
  ...(["tests", "notes"] as const).flatMap((kind): RouteObject[] => [
    {
      path: kind,
      lazy: async () => {
        const { LearningListPage } = await learning();
        return { element: <LearningListPage key={kind} kind={kind} /> };
      },
    },
    {
      path: `${kind}/new`,
      lazy: async () => {
        const { UploadPage } = await upload();
        return { element: <UploadPage key={kind} kind={kind} /> };
      },
    },
    {
      path: `${kind}/:id`,
      lazy: async () => {
        const { LearningDetailPage } = await learningDetail();
        return { element: <LearningDetailPage key={kind} kind={kind} /> };
      },
    },
  ]),
  { path: "account", ...page(() => import("@/features/auth/pages/AccountPage"), "AccountPage") },
];

const adminOnlyRoutes: RouteObject[] = [
  {
    path: "students",
    ...page(() => import("@/features/students/pages/StudentsPage"), "StudentsPage"),
  },
  {
    path: "students/new",
    ...page(() => import("@/features/students/pages/AdmissionPage"), "AdmissionPage"),
  },
  {
    path: "students/:id",
    ...page(() => import("@/features/students/pages/StudentDetailPage"), "StudentDetailPage"),
  },
  { path: "fees", ...page(() => import("@/features/fees/pages/FeesPage"), "FeesPage") },
  {
    path: "fees/accounts/:id",
    ...page(() => import("@/features/fees/pages/FeeAccountPage"), "FeeAccountPage"),
  },
  {
    path: "enquiries",
    ...page(() => import("@/features/enquiries/pages/EnquiriesPage"), "EnquiriesPage"),
  },
  {
    path: "enquiries/new",
    ...page(() => import("@/features/enquiries/pages/NewEnquiryPage"), "NewEnquiryPage"),
  },
  {
    path: "enquiries/:id",
    ...page(() => import("@/features/enquiries/pages/EnquiryDetailPage"), "EnquiryDetailPage"),
  },
  { path: "users", ...page(() => import("@/features/users/pages/UsersPage"), "UsersPage") },
  {
    path: "users/:id",
    ...page(() => import("@/features/users/pages/UserDetailPage"), "UserDetailPage"),
  },
  {
    path: "academics",
    ...page(() => import("@/features/academics/pages/AcademicsPage"), "AcademicsPage"),
  },
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
      {
        index: true,
        ...page(() => import("@/features/portal/pages/PortalHomePage"), "PortalHomePage"),
      },
      {
        path: "tests",
        ...page(() => import("@/features/portal/pages/PortalTestsPage"), "PortalTestsPage"),
      },
      {
        path: "tests/:id",
        ...page(
          () => import("@/features/portal/pages/PortalTestDetailPage"),
          "PortalTestDetailPage",
        ),
      },
      {
        path: "notes",
        ...page(() => import("@/features/portal/pages/PortalNotesPage"), "PortalNotesPage"),
      },
      {
        path: "fees",
        ...page(() => import("@/features/portal/pages/PortalFeesPage"), "PortalFeesPage"),
      },
    ],
  },
  { path: "account", ...page(() => import("@/features/auth/pages/AccountPage"), "AccountPage") },
];

export const routes: RouteObject[] = [
  {
    // One error page and one first-load spinner for the whole app; new pages open at the top.
    element: (
      <>
        <ScrollRestoration />
        <Outlet />
      </>
    ),
    errorElement: <RouteError />,
    hydrateFallbackElement: <FullPageLoader />,
    children: [
      { path: "/", element: <HomeRedirect /> },
      { path: "/login", ...page(() => import("@/features/auth/pages/LoginPage"), "LoginPage") },
      {
        path: "/reset-password",
        ...page(() => import("@/features/auth/pages/ResetPasswordPage"), "ResetPasswordPage"),
      },
      {
        path: "/enquire",
        ...page(() => import("@/features/enquiries/pages/PublicEnquiryPage"), "PublicEnquiryPage"),
      },
      {
        path: "/staff",
        element: <RequireAuth roles={["ADMIN", "TEACHER"]} />,
        children: [
          {
            element: <StaffShell />,
            children: [
              {
                // Inside the shell, so a crashing page keeps the menu and the rest of the app.
                errorElement: <RouteError inShell />,
                children: [
                  ...staffRoutes,
                  { element: <RequireAuth roles={["ADMIN"]} />, children: adminOnlyRoutes },
                ],
              },
            ],
          },
        ],
      },
      {
        path: "/portal",
        element: <RequireAuth roles={["PORTAL"]} />,
        children: [
          {
            element: <PortalShell />,
            children: [{ errorElement: <RouteError inShell />, children: portalRoutes }],
          },
        ],
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
    ],
  },
];

export const router = createBrowserRouter(routes);
