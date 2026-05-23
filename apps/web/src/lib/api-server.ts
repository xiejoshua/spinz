import "server-only";

import { cookies } from "next/headers";

// Server-side fetch goes directly to the backend (NOT through Next.js
// rewrites — those only apply to inbound HTTP requests, not outbound
// fetches from the runtime). Keeps the env var name consistent with
// next.config.mjs's rewrite destination.
const API_BACKEND_URL = process.env.API_BACKEND_URL ?? "http://localhost:8000";

export class ServerApiError extends Error {
  constructor(
    public status: number,
    public statusText: string
  ) {
    super(`${status} ${statusText}`);
    this.name = "ServerApiError";
  }
}

export async function serverApiGet<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const response = await fetch(new URL(path, API_BACKEND_URL), {
    headers: { Cookie: cookieHeader, Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ServerApiError(response.status, response.statusText);
  }
  return (await response.json()) as T;
}
