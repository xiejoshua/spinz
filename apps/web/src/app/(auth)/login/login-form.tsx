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
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {pendingDeletion ? (
          <DeletionPendingBanner
            scheduledDate={scheduledDate}
            submitting={form.formState.isSubmitting}
            onCancel={handleCancelDeletion}
            onDismiss={() => setPendingDeletion(null)}
          />
        ) : rootError ? (
          <FormAlert message={rootError} />
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
              <div className="pt-1 text-right">
                <Link
                  href="/forgot-password"
                  className="font-mono uppercase hover:underline"
                  style={{
                    fontSize: "11px",
                    letterSpacing: "0.12em",
                    color: "var(--muted)",
                  }}
                >
                  Forgot password?
                </Link>
              </div>
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Logging in…" : "Log in"}
        </Button>
        <p
          className="pt-2 text-center font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--muted)",
          }}
        >
          New here?{" "}
          <Link href="/signup" className="hover:underline" style={{ color: "var(--foreground)" }}>
            Create an account
          </Link>
        </p>
      </form>
    </Form>
  );
}

/**
 * Editorial deletion-pending banner. Matches the `<Section tone="danger">`
 * helper in data-settings.tsx — mono-uppercase eyebrow + hairline rule in
 * `--danger`, sans body in `--muted`, then a row of actions. No filled
 * card shell; the danger tone is carried by the eyebrow + rule + button
 * variant, not a tinted background.
 */
function DeletionPendingBanner({
  scheduledDate,
  submitting,
  onCancel,
  onDismiss,
}: {
  scheduledDate: string | null;
  submitting: boolean;
  onCancel: () => void;
  onDismiss: () => void;
}) {
  return (
    <section role="alert" className="space-y-3">
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
      <div className="h-px" style={{ background: "var(--danger)", opacity: 0.6 }} />
      <p
        className="pt-1 font-sans text-[14px] leading-[1.55]"
        style={{ color: "var(--muted)", maxWidth: "60ch" }}
      >
        {scheduledDate
          ? `This account is scheduled for deletion on ${scheduledDate}. Cancel it to sign in.`
          : "This account is scheduled for deletion. Cancel it to sign in."}
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
        <Button
          type="button"
          variant="destructive"
          size="sm"
          disabled={submitting}
          onClick={onCancel}
        >
          {submitting ? "Cancelling…" : "Cancel deletion and sign in"}
        </Button>
        <a
          href={`mailto:${RECOVERY_EMAIL}`}
          className="font-mono uppercase hover:underline"
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--muted)",
          }}
        >
          Recover a deleted account
        </a>
        <button
          type="button"
          onClick={onDismiss}
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
    </section>
  );
}

/** Generic editorial error alert — hairline + danger eyebrow, no fill. */
function FormAlert({ message }: { message: string }) {
  return (
    <section role="alert" className="space-y-2">
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--danger)",
        }}
      >
        Error
      </div>
      <div className="h-px" style={{ background: "var(--danger)", opacity: 0.6 }} />
      <p
        className="pt-1 font-sans text-[14px] leading-[1.55]"
        style={{ color: "var(--foreground)" }}
      >
        {message}
      </p>
    </section>
  );
}
