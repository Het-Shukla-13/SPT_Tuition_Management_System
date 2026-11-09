import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api/envelope";

/**
 * Server-state cache for the whole app.
 * - Don't retry 4xx errors (they won't fix themselves); retry network/5xx twice.
 * - Data counts as fresh for 30 s, so moving between screens doesn't refetch everything.
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: false },
    },
  });
}
