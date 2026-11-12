import { useEffect } from "react";

const APP = "Chalkboard";

/** "Fees · Chalkboard" in the browser tab, history and screen-reader page announcements. */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP}` : APP;
  }, [title]);
}
