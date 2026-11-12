/** Staff dashboard (backend: GET /api/v1/staff/dashboard/). Admins also get fees; teachers never do. */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

// A hand-built dict on the server, so it has no generated type.
export type Dashboard = {
  students: {
    active: number;
    on_hold: number;
    left: number;
    completed: number;
    new_admissions: number;
    new_admissions_days: number;
    active_by_standard: { standard__name: string; standard__level: number; count: number }[];
    recent_admissions: {
      id: number;
      admission_number: string;
      name: string;
      standard: string;
      board: string;
      admission_date: string;
    }[];
  };
  learning: {
    upcoming_tests_7_days: number;
    tests_to_grade: number;
    recent_tests: LearningItem[];
    recent_notes: LearningItem[];
  };
  fees?: {
    scope: string;
    accounts: number;
    students_with_pending_fees: number;
    students_fully_paid: number;
    total_outstanding: string;
    total_collected: string;
    total_credit: string;
    overdue: number;
    ending_soon_with_dues: number;
    recent_payments: {
      id: number;
      student: string;
      amount: string;
      method: string;
      entry_date: string;
      receipt_number: string | null;
      reversed: boolean;
    }[];
  };
};
type LearningItem = {
  id: number;
  title: string;
  subject: string;
  standard: string;
  created_at: string;
};

export function useDashboard(params: { board?: string }) {
  const query = params.board ? { board: params.board } : {};
  return useQuery({
    queryKey: ["staff", "dashboard", query],
    queryFn: () => api.get<Dashboard>("staff/dashboard/", query),
  });
}

/** How many enquiries are still waiting for a first call (admins). */
export function useNewEnquiryCount(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "enquiries", "new-count"],
    queryFn: async () =>
      (await api.list("admin/enquiries/", { status: "NEW", page_size: 1 })).meta?.total_count ?? 0,
    enabled,
  });
}
