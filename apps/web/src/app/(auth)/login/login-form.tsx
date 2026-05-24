"use client";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { ApiError, apiClient } from "@/lib/api-client";
import { type LoginFormValues, loginSchema } from "@/lib/auth-schemas";
import { setApiFormErrors, zodResolver } from "@/lib/forms";
import { type SanitizedUser, useAuthStore } from "@/stores/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

const RECOVERY_EMAIL = "appeals@auxd.xiejoshua.com";

type DeletionPendingState = {
  scheduled_for: string | null;
};

export function LoginForm() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);
  const [pendingDeletion, setPendingDeletion] = useState<DeletionPendingState | null>(null);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function submit(values: LoginFormValues, cancelDeletion = false) {
    try {
      const user = await apiClient.post<SanitizedUser>("/api/v1/auth/login", {
        ...values,
        cancel_deletion: cancelDeletion,
      });
      setUser(user);
      setPendingDeletion(null);
      router.push("/feed");
    } catch (error) {
      if (error instanceof ApiError) {
        const detail = (error.detail as { detail?: unknown } | undefined)?.detail as
          | { error?: string; scheduled_for?: string | null }
          | undefined;
        if (error.status === 403 && detail?.error === "account_deletion_pending") {
          setPendingDeletion({ scheduled_for: detail.scheduled_for ?? null });
          form.clearErrors("root");
          return;
        }
        if (error.status === 401) {
          form.setError("root", { message: "Wrong email or password." });
          setPendingDeletion(null);
          return;
        }
        if (error.status === 429) {
          form.setError("root", {
            message: "Too many attempts. Try again in a few minutes.",
          });
          setPendingDeletion(null);
          return;
        }
        // Pass error.detail (the JSON body) — see signup-form.tsx for the
        // double-nesting trap if you pass `error` directly.
        const handled = setApiFormErrors(
          form,
          error.detail as Parameters<typeof setApiFormErrors>[1]
        );
        if (!handled) {
          form.setError("root", { message: `Login failed (${error.status}).` });
        }
        return;
      }
      form.setError("root", { message: "Could not reach the server. Try again." });
    }
  }

  const onSubmit = (values: LoginFormValues) => submit(values, false);

  function handleCancelDeletion() {
    void submit(form.getValues(), true);
  }

  const rootError = form.formState.errors.root?.message;
  const scheduledDate = pendingDeletion?.scheduled_for
    ? new Date(pendingDeletion.scheduled_for).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <Form {...form}>
      {/* noValidate disables HTML5 native validation so RHF + Zod own the error UX. */}
      {/* Without it, type="email" intercepts submit with the browser's own tooltip. */}
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {pendingDeletion ? (
          <div
            role="alert"
            className="space-y-3 rounded-md p-4"
            style={{
              background: "color-mix(in oklab, var(--danger) 6%, transparent)",
              border: "1px solid var(--danger)",
            }}
          >
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "11px",
                letterSpacing: "0.18em",
                color: "var(--danger)",
              }}
            >
              Pending deletion
            </div>
            <p
              className="font-sans text-[14px] leading-[1.55]"
              style={{ color: "var(--foreground)" }}
            >
              {scheduledDate
                ? `This account is scheduled for deletion on ${scheduledDate}. Cancel it to sign in.`
                : "This account is scheduled for deletion. Cancel it to sign in."}
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={form.formState.isSubmitting}
                onClick={handleCancelDeletion}
              >
                {form.formState.isSubmitting ? "Cancelling…" : "Cancel deletion and sign in"}
              </Button>
              <button
                type="button"
                onClick={() => setPendingDeletion(null)}
                className="font-mono uppercase hover:underline"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.12em",
                  color: "var(--muted)",
                }}
              >
                Keep scheduled
              </button>
            </div>
          </div>
        ) : rootError ? (
          <p
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
          >
            {rootError}
          </p>
        ) : null}
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" autoComplete="email" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Password</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="current-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Logging in…" : "Log in"}
        </Button>
        <div
          className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 pt-2 font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--muted)",
          }}
        >
          <a href={`mailto:${RECOVERY_EMAIL}`} className="hover:underline">
            Forgot password?
          </a>
          <span aria-hidden="true">·</span>
          <Link href="/signup" className="hover:underline">
            Sign up
          </Link>
        </div>
      </form>
    </Form>
  );
}
