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
import { zodResolver } from "@/lib/forms";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const forgotPasswordSchema = z.object({
  email: z.string().email("Enter a valid email address"),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

/**
 * Single-field reset-request form. The backend always returns 200
 * with ``{ok, message}`` — there is no enumeration channel. We mirror
 * that on the client: any successful response flips to the generic
 * success state regardless of body content. Only true network errors
 * keep the form visible (so the user can retry).
 *
 * The component owns the entire page chrome (eyebrow + headline +
 * description) so the request and success states swap atomically.
 * Previously the parent ``page.tsx`` rendered a separate header and
 * the success state stacked a second one underneath — both visible
 * at once.
 */
export function ForgotPasswordForm() {
  const [submitted, setSubmitted] = useState(false);

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: ForgotPasswordFormValues) {
    try {
      await apiClient.post<{ ok: boolean; message: string }>(
        "/api/v1/auth/forgot-password",
        values
      );
      setSubmitted(true);
    } catch (error) {
      if (error instanceof ApiError) {
        // The endpoint is documented as always-200 for enumeration
        // resistance — anything else is a server/rate-limit issue.
        if (error.status === 429) {
          form.setError("root", {
            message: "Too many attempts. Try again in a few minutes.",
          });
          return;
        }
        form.setError("root", {
          message: `Something went wrong (${error.status}). Try again.`,
        });
        return;
      }
      form.setError("root", { message: "Couldn't reach the server. Try again." });
    }
  }

  if (submitted) {
    return <SuccessView />;
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <div className="space-y-8">
      <Header
        eyebrow="Forgot password"
        headline="Reset your password."
        description="Enter the email on your account. We’ll send a link to set a new password."
      />
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
          {rootError ? <FormAlert message={rootError} /> : null}
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
          <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Sending…" : "Send reset link"}
          </Button>
          <p
            className="pt-2 text-center font-mono uppercase"
            style={{
              fontSize: "11px",
              letterSpacing: "0.12em",
              color: "var(--muted)",
            }}
          >
            Remembered it?{" "}
            <Link href="/login" className="hover:underline" style={{ color: "var(--foreground)" }}>
              Back to log in
            </Link>
          </p>
        </form>
      </Form>
    </div>
  );
}

/**
 * Generic success state. The same screen renders whether the email
 * exists, was unverified, or matched a deletion-pending account —
 * the backend never tells us which (FR-141, no enumeration). The
 * copy below is deliberately ambiguous.
 */
function SuccessView() {
  return (
    <div className="space-y-8">
      <Header
        eyebrow="Check your inbox"
        headline="If that email is registered, we sent a reset link."
        description="The link expires in one hour. Check your spam folder if it doesn’t arrive in the next few minutes."
      />
      <Button asChild className="w-full">
        <Link href="/login">Back to log in</Link>
      </Button>
    </div>
  );
}

/** Editorial page header: mono eyebrow + Newsreader headline + muted body. */
function Header({
  eyebrow,
  headline,
  description,
}: {
  eyebrow: string;
  headline: string;
  description: string;
}) {
  return (
    <div className="space-y-3">
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--muted)",
        }}
      >
        {eyebrow}
      </div>
      <h1
        className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
        style={{
          fontSize: "clamp(32px, 5vw, 44px)",
          color: "var(--foreground)",
          fontFamily: "var(--font-serif)",
        }}
      >
        {headline}
      </h1>
      <p
        className="font-sans text-[16px] leading-[1.55]"
        style={{ color: "var(--muted)", maxWidth: "60ch" }}
      >
        {description}
      </p>
    </div>
  );
}

/** Editorial inline error — matches /login's FormAlert shape. */
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
