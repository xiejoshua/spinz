"use client";

import { initPostHogBrowser } from "@/lib/posthog";
import { getQueryClient } from "@/lib/query-client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { type ReactNode, useEffect } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  useEffect(() => {
    initPostHogBrowser();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
