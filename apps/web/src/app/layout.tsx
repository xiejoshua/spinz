import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { Providers } from "@/providers";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "auxd — Social album tracker",
  description: "Log albums in under 8 seconds. Discover from the people you follow.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans">
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );
}
