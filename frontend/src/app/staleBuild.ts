const RELOADED_KEY = "chalkboard:reloaded-for-update";

/**
 * After a new version is deployed, a tab that was already open asks for page
 * files that no longer exist. One automatic reload fetches the new version.
 */
export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS/i.test(
    message,
  );
}

export function reloadOnceForUpdate(): boolean {
  try {
    if (sessionStorage.getItem(RELOADED_KEY)) return false;
    sessionStorage.setItem(RELOADED_KEY, "1");
  } catch {
    return false; // storage blocked: show the error page instead of looping
  }
  window.location.reload();
  return true;
}

/** Once a page has loaded fine, a later stale-build error may reload again. */
export function clearReloadFlag() {
  try {
    sessionStorage.removeItem(RELOADED_KEY);
  } catch {
    /* storage blocked: nothing to clear */
  }
}
