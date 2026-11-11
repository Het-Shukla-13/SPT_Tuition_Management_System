import { useEffect, useRef, useState } from "react";

import { GOOGLE_CLIENT_ID } from "@/lib/config";

/**
 * Google's own "Sign in with Google" button (Google Identity Services).
 * Google hands us an ID token; the backend verifies it. Renders nothing when
 * no client id is configured or Google's script can't load (e.g. blocked).
 */
type GoogleId = {
  initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
};
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error("Google script failed to load"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export function GoogleButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    callback.current = onCredential;
  });

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadScript()
      .then(() => {
        const google = window.google?.accounts.id;
        if (cancelled || !google || !box.current) return;
        google.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => callback.current(response.credential),
        });
        google.renderButton(box.current, {
          theme: "outline",
          size: "large",
          shape: "rectangular",
          text: "continue_with",
          width: box.current.offsetWidth || 340,
        });
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!GOOGLE_CLIENT_ID || failed) return null;
  return <div ref={box} className="flex min-h-11 w-full justify-center" />;
}
