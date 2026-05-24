"use client";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { ApiError, apiClient } from "@/lib/api-client";
import { setApiFormErrors, zodResolver } from "@/lib/forms";
import { type SanitizedUser, useAuthStore } from "@/stores/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

/**
 * Mirrors the signup password rules in lib/auth-schemas.ts and the
 * backend ``_PASSWORD_MIN_LEN`` in auth/service.py. The "≥1 letter,
 * ≥1 digit" check is enforced server-side via ``validate_password_policy``;
 * we mirror it here only for the field-level UX, not authoritatively.
 */
const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(12, "Password must be at least 12 characters")
      .max(128, "Password must be at most 128 characters")
      .regex(/[A-Za-z]/, "Password must contain at least one letter")
      .regex(/\d/, "Password must contain at least one digit"),
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordForm({ token }: { token: string }) {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);
  const [linkInvalid, setLinkInvalid] = useState(false);

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: ResetPasswordFormValues) {
    try {
      const user = await apiClient.post<SanitizedUser>("/api/v1/auth/reset-password", {
        token,
        new_password: values.new_password,
      });
      setUser(user);
      router.push("/feed");
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 410) {
          setLinkInvalid(true);
          return;
        }
        if (error.status === 429) {
          form.setError("root", {
            message: "Too many attempts. Try again in a few minutes.",
          });
          return;
        }
        const handled = setApiFormErrors(
          form,
          error.detail as Parameters<typeof setApiFormErrors>[1]
        );
        if (!handled) {
          form.setError("root", { message: `Couldn't reset password (${error.status}).` });
        }
        return;
      }
      form.setError("root", { message: "Couldn't reach the server. Try again." });
    }
  }

  if (linkInvalid) {
    return <ExpiredView />;
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {rootError ? <FormAlert message={rootError} /> : null}
        <FormField
          control={form.control}
          name="new_password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>New password</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormDescription>
                At least 12 characters, including a letter and a digit.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="confirm_password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Confirm new password</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Saving…" : "Reset password"}
        </Button>
      </form>
    </Form>
  );
}

/** 410 — token used / expired / unknown. Editorial Section-danger shape. */
function ExpiredView() {
  return (
    <div className="space-y-8">
      <section role="alert" className="space-y-3">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--danger)",
          }}
        >
          Link expired
        </div>
        <div className="h-px" style={{ background: "var(--danger)", opacity: 0.6 }} />
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
        <p
          className="font-sans text-[16px] leading-[1.55]"
          style={{ color: "var(--muted)", maxWidth: "60ch" }}
        >
          It may have already been used, or it expired after one hour. Request a fresh one.
        </p>
      </section>
      <Button asChild className="w-full">
        <Link href="/forgot-password">Request a new link</Link>
      </Button>
    </div>
  );
}

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
