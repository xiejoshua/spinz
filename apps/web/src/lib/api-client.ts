// Browser-side API client. All paths are relative — Next.js rewrites
// (see next.config.mjs) proxy /api/v1/* to the backend. This keeps the
// browser on a single origin so session cookies stay first-party.

import { toast } from "@/hooks/use-toast";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail?: unknown
  ) {
    super(`${status} ${statusText}`);
    this.name = "ApiError";
  }
}

/**
 * T159 — when the backend returns a 403 with
 * ``{error: "account_suspended"}`` the user has been suspended by
 * moderators. Redirect the browser to the standalone /suspended page
 * (which lives outside the (app) layout so it works while the cookie
 * still exists).
 *
 * Exported for testing — production code never calls this directly.
 */
export function isAccountSuspendedDetail(detail: unknown): boolean {
  if (!detail || typeof detail !== "object") return false;
  const obj = detail as Record<string, unknown>;
  return obj.error === "account_suspended";
}

/**
 * 002-auth-email-flows — backend ``SessionMiddleware`` returns 403
 * ``{error: "email_unverified", message, resend_endpoint}`` for
 * state-changing requests by users who haven't yet clicked the
 * verification link. The permanent banner in (app)/layout.tsx is
 * already telling them this; we surface a brief toast so the failing
 * action isn't silent and we do NOT redirect (unlike suspension —
 * the user can keep browsing).
 *
 * Exported for testing.
 */
export function isEmailUnverifiedDetail(detail: unknown): boolean {
  if (!detail || typeof detail !== "object") return false;
  const obj = detail as Record<string, unknown>;
  return obj.error === "email_unverified";
}

function maybeRedirectOnSuspension(detail: unknown): void {
  if (typeof window === "undefined") return;
  if (!isAccountSuspendedDetail(detail)) return;
  // Only redirect when we're not already on /suspended — avoid a loop
  // if the suspended page itself happens to fire an API call.
  if (window.location.pathname.startsWith("/suspended")) return;
  window.location.assign("/suspended");
}

function maybeNotifyOnEmailUnverified(detail: unknown): void {
  if (typeof window === "undefined") return;
  if (!isEmailUnverifiedDetail(detail)) return;
  toast({
    title: "Verify your email to continue.",
    variant: "destructive",
  });
}

type FetchOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  searchParams?: Record<string, string | number | boolean | undefined>;
};

const CSRF_COOKIE_NAME = "auxd_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const CSRF_PROTECTED_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function buildUrl(path: string, searchParams?: FetchOptions["searchParams"]): string {
  // Relative URL — browser resolves against the current origin and the
  // request goes through Next.js's rewrites layer.
  if (!searchParams) return path;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (value !== undefined) {
      query.set(key, String(value));
    }
  }
  const search = query.toString();
  return search ? `${path}?${search}` : path;
}

/**
 * T173 — security review fix: read the `auxd_csrf` double-submit cookie
 * the backend's `SessionMiddleware` writes on login (see
 * `apps/api/src/auxd_api/middleware.py`). The cookie is HttpOnly=false
 * exactly so JS can lift the value into the `X-CSRF-Token` header.
 * Returns the empty string on SSR (no `document`) — server-rendered
 * components only do GETs, so CSRF isn't enforced for them anyway.
 */
function readCsrfToken(): string {
  if (typeof document === "undefined") return "";
  const prefix = `${CSRF_COOKIE_NAME}=`;
  for (const raw of document.cookie.split(";")) {
    const trimmed = raw.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return "";
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { body, searchParams, headers, method, ...rest } = options;
  const upperMethod = (method ?? "GET").toUpperCase();
  const csrfHeaders: Record<string, string> = {};
  if (CSRF_PROTECTED_METHODS.has(upperMethod)) {
    const token = readCsrfToken();
    if (token) {
      csrfHeaders[CSRF_HEADER_NAME] = token;
    }
  }
  const response = await fetch(buildUrl(path, searchParams), {
    ...rest,
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...csrfHeaders,
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      // response body wasn't JSON
    }
    if (response.status === 403) {
      maybeRedirectOnSuspension(detail);
      maybeNotifyOnEmailUnverified(detail);
    }
    throw new ApiError(response.status, response.statusText, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * REV-100 — multipart POST helper. The avatar upload sends `FormData`,
 * not JSON, so it can't go through {@link apiFetch} (which always
 * stringifies the body and sets `Content-Type: application/json`).
 * This helper mirrors apiFetch's CSRF wiring (cookie → `X-CSRF-Token`
 * header) so multipart writes are protected by the same double-submit
 * defence T173 added for JSON writes. Importantly, we do **not** set
 * `Content-Type` — the browser must set it itself so the multipart
 * boundary parameter is included.
 *
 * Callers handle their own response parsing (avatar mutation needs the
 * `Response` for both success JSON and error JSON shapes).
 */
export async function apiFetchMultipart(
  path: string,
  formData: FormData,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers);
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }
  // Intentionally do NOT set Content-Type — the browser sets it to
  // `multipart/form-data; boundary=...` when the body is a FormData.
  return fetch(path, {
    ...init,
    method: "POST",
    headers,
    body: formData,
    credentials: "include",
  });
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<FetchOptions, "method" | "body">) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<FetchOptions, "method">) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Omit<FetchOptions, "method">) =>
    apiFetch<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<FetchOptions, "method">) =>
    apiFetch<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<FetchOptions, "method" | "body">) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};
