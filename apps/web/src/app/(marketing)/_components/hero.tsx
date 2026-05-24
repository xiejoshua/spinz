"use client";

import { Button, Chip } from "@heroui/react";

export function Hero() {
  return (
    <section className="w-full" style={{ background: "var(--surface)" }}>
      <div className="mx-auto max-w-6xl px-6 py-24 sm:py-32 lg:py-40">
        <div className="max-w-3xl">
          <h1
            className="font-serif font-bold leading-[1.05] tracking-[-0.02em]"
            style={{
              fontSize: "clamp(48px, 8vw, 88px)",
              color: "var(--foreground)",
            }}
          >
            A diary to bring back{" "}
            <em className="italic" style={{ fontFamily: "var(--font-serif)" }}>
              albums
            </em>{" "}
            as art.
          </h1>
          <p
            className="mt-6 max-w-2xl font-sans text-[18px] leading-[1.55]"
            style={{ color: "var(--muted)" }}
          >
            Half-star ratings. Optional reviews. Eight seconds to log.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Button
              variant="primary"
              size="lg"
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              render={(props) => <a {...(props as any)} href="/signup" />}
            >
              Sign up — it's free
            </Button>
            <a
              href="#wedge"
              className="font-sans text-[14px] underline-offset-4 hover:underline"
              style={{ color: "var(--foreground)" }}
            >
              See how it works ↓
            </a>
          </div>
          <div className="mt-12">
            <Chip variant="soft" size="sm">
              <Chip.Label
                className="font-sans font-medium uppercase"
                style={{ fontSize: "11px", letterSpacing: "0.15em" }}
              >
                In beta
              </Chip.Label>
            </Chip>
          </div>
        </div>
      </div>
    </section>
  );
}
