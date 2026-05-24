"use client";

import { Button } from "@heroui/react";

export function FinalCta() {
  return (
    <>
      <section className="w-full" style={{ background: "var(--background)" }}>
        <div className="mx-auto max-w-3xl px-6 py-32 sm:py-40 text-center">
          <h2
            className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
            style={{
              fontSize: "clamp(40px, 6vw, 64px)",
              color: "var(--foreground)",
            }}
          >
            Start your diary.
          </h2>
          <div className="mt-10 flex flex-col items-center gap-4">
            <Button
              variant="primary"
              size="lg"
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              render={(props) => <a {...(props as any)} href="/signup" />}
            >
              Sign up — it's free
            </Button>
            <a
              href="/login"
              className="font-sans text-[14px] underline-offset-4 hover:underline"
              style={{ color: "var(--muted)" }}
            >
              Already have one? Log in
            </a>
          </div>
        </div>
      </section>
      <footer
        className="w-full"
        style={{
          borderTop: "1px solid var(--separator)",
          background: "var(--background)",
        }}
      >
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div
              className="font-sans font-bold tracking-[-0.02em]"
              style={{ fontSize: "16px", color: "var(--foreground)" }}
            >
              auxd
            </div>
            <div
              className="mt-1 font-sans text-[12px]"
              style={{ color: "var(--muted)" }}
            >
              © 2026 — built in public
            </div>
          </div>
          <nav
            className="flex gap-6 font-sans text-[13px]"
            style={{ color: "var(--muted)" }}
          >
            <a href="https://github.com" className="hover:underline">
              GitHub
            </a>
            <a href="/legal/privacy" className="hover:underline">
              Privacy
            </a>
            <a href="/legal/terms" className="hover:underline">
              Terms
            </a>
          </nav>
        </div>
      </footer>
    </>
  );
}
