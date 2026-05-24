"use client";

import { initPostHogBrowser } from "@/lib/posthog";
import { getQueryClient } from "@/lib/query-client";
import { CacheProvider } from "@emotion/react";
import createCache from "@emotion/cache";
import { ThemeProvider as MuiThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider as NextThemeProvider, useTheme } from "next-themes";
import { type ReactNode, useEffect, useMemo } from "react";

const emotionCache = createCache({ key: "mui", prepend: true });

function MuiBridge({ children }: { children: ReactNode }) {
  const { resolvedTheme } = useTheme();
  const muiTheme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: resolvedTheme === "dark" ? "dark" : "light",
          primary: { main: resolvedTheme === "dark" ? "#F5F5F5" : "#171717" },
          secondary: { main: resolvedTheme === "dark" ? "#E5C76B" : "#D4AF37" },
          background: {
            default: resolvedTheme === "dark" ? "#1B1916" : "#FFFFFF",
            paper: resolvedTheme === "dark" ? "#2A2723" : "#FBF8F1",
          },
          text: {
            primary: resolvedTheme === "dark" ? "#F5F5F5" : "#171717",
            secondary: resolvedTheme === "dark" ? "#A8A8A8" : "#737373",
          },
        },
        typography: {
          fontFamily:
            "var(--font-inter-tight), system-ui, -apple-system, sans-serif",
        },
        shape: { borderRadius: 8 },
        components: {
          MuiButtonBase: { defaultProps: { disableRipple: true } },
          MuiPaper: { defaultProps: { elevation: 0 } },
        },
      }),
    [resolvedTheme]
  );

  return (
    <CacheProvider value={emotionCache}>
      <MuiThemeProvider theme={muiTheme}>
        <CssBaseline enableColorScheme={false} />
        {children}
      </MuiThemeProvider>
    </CacheProvider>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  useEffect(() => {
    initPostHogBrowser();
  }, []);

  return (
    <NextThemeProvider
      attribute="data-theme"
      defaultTheme="auxd"
      value={{ light: "auxd", dark: "auxd-dark" }}
      enableSystem={false}
    >
      <MuiBridge>
        <QueryClientProvider client={queryClient}>
          {children}
          {process.env.NODE_ENV === "development" && (
            <ReactQueryDevtools initialIsOpen={false} />
          )}
        </QueryClientProvider>
      </MuiBridge>
    </NextThemeProvider>
  );
}
