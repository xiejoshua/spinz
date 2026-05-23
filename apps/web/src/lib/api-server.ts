import "server-only";

import { cookies } from "next/headers";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const response = await fetch(new URL(path, API_BASE_URL), {
    headers: { Cookie: cookieHeader, Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ServerApiError(response.status, response.statusText);
  }
  return (await response.json()) as T;
}
