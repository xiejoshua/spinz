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
import { type SignupFormValues, signupSchema } from "@/lib/auth-schemas";
import { setApiFormErrors, zodResolver } from "@/lib/forms";
import { type SanitizedUser, useAuthStore } from "@/stores/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

export function SignupForm() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);

  const form = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: "", password: "", handle: "" },
  });

  async function onSubmit(values: SignupFormValues) {
    try {
      const user = await apiClient.post<SanitizedUser>("/api/v1/auth/signup", values);
      setUser(user);
      router.push("/onboarding/step-1");
    } catch (error) {
      if (error instanceof ApiError) {
        // Pass error.detail (the parsed JSON body, shape {detail: ...}) — the
        // helper reads payload.detail to find the inner {error, message} or
        // Pydantic array. Passing `error` directly would double-nest because
        // `error.detail === response body === {detail: {...}}`.
        const handled = setApiFormErrors(
          form,
          error.detail as Parameters<typeof setApiFormErrors>[1]
        );
        if (!handled) {
          form.setError("root", { message: `Signup failed (${error.status}).` });
        }
        return;
      }
      form.setError("root", { message: "Could not reach the server. Try again." });
    }
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <Form {...form}>
      {/* noValidate disables HTML5 native validation so RHF + Zod own the error UX. */}
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {rootError && (
          <p
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
          >
            {rootError}
          </p>
        )}
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" autoComplete="email" placeholder="you@example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="handle"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Handle</FormLabel>
              <FormControl>
                <Input autoComplete="username" placeholder="yourhandle" {...field} />
              </FormControl>
              <FormDescription>
                3–24 chars, lowercase letters / numbers / underscores.
              </FormDescription>
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
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormDescription>
                At least 12 characters, including a letter and a digit.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating account…" : "Sign up"}
        </Button>
        {/* Single editorial pivot to /login. The recovery CTA for a
            recently-deleted account lives on the deletion-pending
            banner on /login itself (rather than here on signup) so the
            mailto: link only surfaces in the context where the user
            actually saw the "scheduled for deletion" state. */}
        <p
          className="pt-2 text-center font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--muted)",
          }}
        >
          Already have an account?{" "}
          <Link href="/login" className="hover:underline" style={{ color: "var(--foreground)" }}>
            Log in
          </Link>
        </p>
      </form>
    </Form>
  );
}
