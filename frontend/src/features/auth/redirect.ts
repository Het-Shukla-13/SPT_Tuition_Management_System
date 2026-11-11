/**
 * Where to go after logging in. `?next=` comes from the URL, so it's
 * untrusted: only same-site paths are accepted. "//evil.com" or
 * "https://evil.com" would otherwise turn our login page into a phishing
 * redirector.
 */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return null;
  }
  if (next.startsWith("/login") || next.startsWith("/reset-password")) return null;
  return next;
}
