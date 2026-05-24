"use client";

import { Button } from "@heroui/react";
import { ThemeToggle } from "./theme-toggle";

export function TopBar() {
  return (
    <header
      className="sticky top-0 z-50 backdrop-blur-md"
      style={{
        background: "color-mix(in oklab, var(--background) 80%, transparent)",
        borderBottom: "1px solid var(--separator)",
      }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <a
          href="/"
          className="font-sans text-[20px] font-bold tracking-[-0.02em]"
          style={{ color: "var(--foreground)" }}
        >
          auxd
        </a>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            render={(props) => <a {...(props as any)} href="/login" />}
          >
            Log in
          </Button>
          <Button
            variant="primary"
            size="sm"
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            render={(props) => <a {...(props as any)} href="/signup" />}
          >
            Sign up
          </Button>
        </div>
      </div>
    </header>
  );
}
