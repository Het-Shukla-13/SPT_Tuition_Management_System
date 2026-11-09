import {
  ClipboardListIcon,
  HomeIcon,
  IndianRupeeIcon,
  LayoutDashboardIcon,
  type LucideIcon,
  MessageSquareIcon,
  NotebookTextIcon,
  Settings2Icon,
  UserCogIcon,
  UsersIcon,
} from "lucide-react";

import type { Role } from "@/lib/api/types";

export type NavItem = { to: string; label: string; icon: LucideIcon; roles: Role[]; end?: boolean };

/**
 * The staff menu, in ONE place. Each item says which roles see it, so the
 * sidebar, the phone menu and the route guards can't disagree.
 */
export const STAFF_NAV: NavItem[] = [
  {
    to: "/staff",
    label: "Dashboard",
    icon: LayoutDashboardIcon,
    roles: ["ADMIN", "TEACHER"],
    end: true,
  },
  { to: "/staff/students", label: "Students", icon: UsersIcon, roles: ["ADMIN"] },
  { to: "/staff/fees", label: "Fees", icon: IndianRupeeIcon, roles: ["ADMIN"] },
  { to: "/staff/tests", label: "Tests", icon: ClipboardListIcon, roles: ["ADMIN", "TEACHER"] },
  { to: "/staff/notes", label: "Notes", icon: NotebookTextIcon, roles: ["ADMIN", "TEACHER"] },
  { to: "/staff/enquiries", label: "Enquiries", icon: MessageSquareIcon, roles: ["ADMIN"] },
  { to: "/staff/users", label: "Users & invites", icon: UserCogIcon, roles: ["ADMIN"] },
  { to: "/staff/academics", label: "Academics setup", icon: Settings2Icon, roles: ["ADMIN"] },
];

export const PORTAL_NAV = [
  { to: "/portal", label: "Home", icon: HomeIcon, end: true },
  { to: "/portal/tests", label: "Tests", icon: ClipboardListIcon },
  { to: "/portal/notes", label: "Notes", icon: NotebookTextIcon },
  { to: "/portal/fees", label: "Fees", icon: IndianRupeeIcon },
] as const;

export function staffNavFor(role: Role) {
  return STAFF_NAV.filter((item) => item.roles.includes(role));
}
