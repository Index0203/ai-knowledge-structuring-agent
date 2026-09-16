const DEFAULT_API_BASE_URL = "http://localhost:8000";

function isLoopbackHost(hostname: string): boolean {
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname === "[::1]"
  );
}

function hostOf(url: string): string | null {
  const match = /^https?:\/\/([^/:]+)/i.exec(url.trim());
  return match ? match[1].toLowerCase() : null;
}

function portOf(url: string, fallback: string): string {
  const match = /^https?:\/\/[^/]+?:(\d+)(?:\/|$)/i.exec(url.trim());
  return match ? match[1] : fallback;
}

/**
 * The API address the browser should call.
 *
 * `NEXT_PUBLIC_API_BASE_URL` is inlined when the app is built, which normally
 * pins the deployed address. A page opened over the LAN (for example
 * `http://192.168.1.10:3000`) therefore talks to the API on the same host, so a
 * single link works for every device on the network without rebuilding. An
 * explicitly configured remote API (anything that is not localhost) is left
 * untouched.
 */
export function resolveApiBaseUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim();
  const fallback = configured || DEFAULT_API_BASE_URL;
  if (typeof window === "undefined") return fallback;

  const hostname = window.location.hostname;
  if (!hostname || isLoopbackHost(hostname)) return fallback;

  const configuredHost = configured ? hostOf(configured) : null;
  if (configuredHost && !isLoopbackHost(configuredHost)) return fallback;

  const port = configured ? portOf(configured, "8000") : "8000";
  return `${window.location.protocol}//${hostname}:${port}`;
}

const apiBaseUrl = resolveApiBaseUrl();

export { apiBaseUrl };
