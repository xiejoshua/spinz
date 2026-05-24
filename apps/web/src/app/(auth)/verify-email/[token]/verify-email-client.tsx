"use client";

import { Button } from "@/components/ui/button";
import { ApiError, apiClient } from "@/lib/api-client";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef } from "react";

type VerifyResponse = {
  verified: boolean;
  idempotent: boolean;
};

type State =
  | { kind: "pending" }
  | { kind: "success"; idempotent: boolean }
  | { kind: "expired" }
  | { kind: "error" };

/**
 * Fires a single POST /api/v1/auth/verify-email on mount and renders
 * one of four editorial states. The ref-guard around the kickoff
 * effect prevents React 18 strict-mode double-mount from firing the
 * mutation twice — the backend is idempotent on the second attempt,
 * but the second call would consume a fresh DB lookup and the user
 * would briefly see the "pending" spinner flicker.
 */
export function VerifyEmailClient({ token }: { token: string }) {
  const mutation = useMutation({
    mutationFn: async () => apiClient.post<VerifyResponse>("/api/v1/auth/verify-email", { token }),
  });

  const kickedOffRef = useRef(false);
  const mutate = mutation.mutate;
  useEffect(() => {
    if (kickedOffRef.current) return;
    kickedOffRef.current = true;
    mutate();
  }, [mutate]);

  const state: State = ((): State => {
    if (mutation.isPending || mutation.isIdle) return { kind: "pending" };
    if (mutation.isSuccess) {
      return { kind: "success", idempotent: Boolean(mutation.data?.idempotent) };
    }
    if (mutation.error instanceof ApiError && mutation.error.status === 410) {
      return { kind: "expired" };
    }
    return { kind: "error" };
  })();

  if (state.kind === "pending") return <PendingView />;
  if (state.kind === "success") return <SuccessView idempotent={state.idempotent} />;
  if (state.kind === "expired") return <ExpiredView />;
  return <NetworkErrorView onRetry={() => mutation.mutate()} pending={mutation.isPending} />;
}

function Eyebrow({
  tone = "default",
  children,
}: { tone?: "default" | "danger"; children: string }) {
  return (
    <div
      className="font-mono uppercase"
      style={{
        fontSize: "11px",
        letterSpacing: "0.18em",
        color: tone === "danger" ? "var(--danger)" : "var(--muted)",
      }}
    >
      {children}
    </div>
  );
}

function Headline({ children }: { children: string }) {
  return (
    <h1
      className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
      style={{
        fontSize: "clamp(32px, 5vw, 44px)",
        color: "var(--foreground)",
        fontFamily: "var(--font-serif)",
      }}
    >
      {children}
    </h1>
  );
}

function Body({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="font-sans text-[16px] leading-[1.55]"
      style={{ color: "var(--muted)", maxWidth: "60ch" }}
    >
      {children}
    </p>
  );
}

function DangerRule() {
  return <div className="h-px" style={{ background: "var(--danger)", opacity: 0.6 }} />;
}

function PendingView() {
  return (
    <div className="space-y-3">
      <Eyebrow>Verifying</Eyebrow>
      <Headline>One moment.</Headline>
      <Body>Confirming your email…</Body>
    </div>
  );
}

function SuccessView({ idempotent }: { idempotent: boolean }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Eyebrow>{idempotent ? "Already verified" : "Verified"}</Eyebrow>
        <Headline>{idempotent ? "Already verified." : "Email verified."}</Headline>
        <Body>You&rsquo;re all set.</Body>
      </div>
      <Button asChild className="w-full">
        <Link href="/feed">Go to your feed</Link>
      </Button>
    </div>
  );
}

function ExpiredView() {
  return (
    <div className="space-y-8">
      <section role="alert" className="space-y-3">
        <Eyebrow tone="danger">Link expired</Eyebrow>
        <DangerRule />
        <h1
          className="pt-1 font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          This link is no longer valid.
        </h1>
        <Body>
          It may have already been used, or it expired after 24 hours. Sign in to request a fresh
          one.
        </Body>
      </section>
      <div className="flex flex-col gap-3">
        <Button asChild className="w-full">
          <Link href="/login">Back to log in</Link>
        </Button>
        <Link
          href="/forgot-password"
          className="text-center font-mono uppercase hover:underline"
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--muted)",
          }}
        >
          Forgot password?
        </Link>
      </div>
    </div>
  );
}

function NetworkErrorView({ onRetry, pending }: { onRetry: () => void; pending: boolean }) {
  return (
    <div className="space-y-8">
      <section role="alert" className="space-y-3">
        <Eyebrow tone="danger">Error</Eyebrow>
        <DangerRule />
        <Headline>Couldn&rsquo;t reach the server.</Headline>
        <Body>Check your connection and try again.</Body>
      </section>
      <Button type="button" className="w-full" onClick={onRetry} disabled={pending}>
        {pending ? "Retrying…" : "Try again"}
      </Button>
    </div>
  );
}
