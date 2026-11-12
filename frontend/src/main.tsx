import "./styles/index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { Providers } from "@/app/providers";
import { clearReloadFlag } from "@/app/staleBuild";
import { router } from "@/app/router";
import { createQueryClient } from "@/lib/query";

const queryClient = createQueryClient();
// If this version keeps running fine, a later update may auto-reload once again.
setTimeout(clearReloadFlag, 10_000);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
);
