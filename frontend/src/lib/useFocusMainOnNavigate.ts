import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

/** The id of each shell's <main>, the skip link's target. */
export const MAIN_ID = "main";

/**
 * After moving to another page, put keyboard and screen-reader focus on the
 * page content (not the old link), like a normal page load would.
 */
export function useFocusMainOnNavigate<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    ref.current?.focus({ preventScroll: true });
  }, [pathname]);
  return ref;
}
