/**
 * The in-memory login state.
 *
 * - The access token lives ONLY in this module's memory: never localStorage,
 *   so a malicious script can't read a stored token.
 * - The refresh token is an HttpOnly cookie the browser handles; we never see it.
 * - Logging out in one tab tells the other tabs (BroadcastChannel).
 */

type Listener = () => void;

let accessToken: string | null = null;
let endedReason: string | null = null;
const listeners = new Set<Listener>();

const channel: BroadcastChannel | null =
  typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("chalkboard-auth") : null;

function emit() {
  for (const listener of listeners) listener();
}

export const session = {
  getAccessToken: () => accessToken,

  setAccessToken(token: string) {
    accessToken = token;
    endedReason = null;
    emit();
  },

  /** Why the last session ended (an error_code), for the login page message. */
  getEndedReason: () => endedReason,

  /** Forget the login here. `broadcast` also logs out the other open tabs. */
  clear(reason: string | null = null, broadcast = true) {
    accessToken = null;
    endedReason = reason;
    if (broadcast) channel?.postMessage({ type: "logout" });
    emit();
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

channel?.addEventListener("message", (event: MessageEvent<{ type?: string }>) => {
  if (event.data?.type === "logout") session.clear(null, false);
});
