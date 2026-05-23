"use client";

import { ApiError, apiClient } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";

type HealthzResponse = { status: string };

export function HealthCheck() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["healthz"],
    queryFn: () => apiClient.get<HealthzResponse>("/healthz"),
  });

  if (isLoading) {
    return <span className="text-sm text-muted-foreground">checking API…</span>;
  }
  if (error) {
    const message = error instanceof ApiError ? error.message : "unreachable";
    return <span className="text-sm text-destructive">API {message}</span>;
  }
  return <span className="text-sm text-muted-foreground">API: {data?.status}</span>;
}
