import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { NuqsAdapter } from "nuqs/adapters/react-router/v8";
import { type ReactNode, useEffect } from "react";
import { Toaster } from "sonner";

import { ME_KEY } from "@/features/auth/session";
import { session } from "@/lib/api/session";

/**
 * App-wide providers. Also: when the session ends anywhere (refresh failed,
 * logout in another tab), drop every cached response so no private data
 * stays in memory, and mark the user as logged out (guards then show login).
 */
export function Providers({
  queryClient,
  children,
}: {
  queryClient: QueryClient;
  children: ReactNode;
}) {
  useEffect(
    () =>
      session.subscribe(() => {
        if (session.getAccessToken() !== null) return;
        if (queryClient.getQueryData(ME_KEY) === null) return;
        queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== ME_KEY[0] });
        queryClient.setQueryData(ME_KEY, null);
      }),
    [queryClient],
  );

  return (
    <QueryClientProvider client={queryClient}>
      <NuqsAdapter>{children}</NuqsAdapter>
      <Toaster position="top-center" richColors closeButton />
    </QueryClientProvider>
  );
}
