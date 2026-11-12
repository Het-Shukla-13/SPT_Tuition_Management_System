import { useNavigation } from "react-router";

import { MAIN_ID } from "@/lib/useFocusMainOnNavigate";
import { cn } from "@/lib/utils";

/** First thing a keyboard user reaches: jumps past the menu to the page. */
export function SkipLink() {
  return (
    <a
      href={`#${MAIN_ID}`}
      className="sr-only z-50 rounded-[var(--radius-control)] bg-primary px-4 py-3 font-bold text-white focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
    >
      Skip to content
    </a>
  );
}

/** A thin bar at the top while the next page (or its code) is loading. */
export function NavigationProgress() {
  const busy = useNavigation().state !== "idle";
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px] origin-left bg-chalk transition-transform duration-500",
        busy ? "scale-x-75" : "scale-x-0 duration-0",
      )}
    />
  );
}
