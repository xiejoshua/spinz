// Browser-side API client. All paths are relative — Next.js rewrites
// (see next.config.mjs) proxy /api/v1/* to the backend. This keeps the
// browser on a single origin so session cookies stay first-party.

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

type FetchOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  searchParams?: Record<string, string | number | boolean | undefined>;
};

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

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { body, searchParams, headers, ...rest } = options;
  const response = await fetch(buildUrl(path, searchParams), {
    ...rest,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
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
    throw new ApiError(response.status, response.statusText, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
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
