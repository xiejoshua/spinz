import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { Providers } from "@/providers";
import type { Metadata, Viewport } from "next";
import { Inter_Tight, JetBrains_Mono, Newsreader } from "next/font/google";
import type { ReactNode } from "react";

const newsreader = Newsreader({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-newsreader",
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

const interTight = Inter_Tight({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter-tight",
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "auxd — A diary to bring back albums as art.",
  description:
    "A diary to bring back albums as art. Half-star ratings. Optional reviews. Eight seconds to log.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

// Critical accent tokens — inlined in <head> so they apply BEFORE any
// external stylesheet (notably HeroUI's default theme) has a chance to
// flash its saas-blue accent on first paint or hard refresh.
const CRITICAL_TOKENS = `
[data-theme="auxd"]{--accent:oklch(0.40 0.12 25);--accent-foreground:#fff;--link:oklch(0.40 0.12 25);--focus:oklch(0.40 0.12 25);--background:#fff;--foreground:oklch(0.205 0 0);--surface:oklch(98% 0.012 80);--muted:oklch(0.55 0 0);--gold:oklch(0.74 0.13 87);--border:oklch(0.91 0 0);--separator:oklch(0.93 0 0);color-scheme:light}
[data-theme="auxd-dark"]{--accent:oklch(0.65 0.14 25);--accent-foreground:oklch(0.13 0.003 80);--link:oklch(0.72 0.12 25);--focus:oklch(0.65 0.14 25);--background:oklch(0.13 0.003 80);--foreground:oklch(0.96 0 0);--surface:oklch(0.19 0.005 80);--muted:oklch(0.66 0 0);--gold:oklch(0.80 0.13 87);--border:oklch(0.27 0 0);--separator:oklch(0.24 0 0);color-scheme:dark}
html,body{background:var(--background);color:var(--foreground)}
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="auxd"
      suppressHydrationWarning
      className={`${newsreader.variable} ${interTight.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <style dangerouslySetInnerHTML={{ __html: CRITICAL_TOKENS }} />
      </head>
      <body>
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );
}
