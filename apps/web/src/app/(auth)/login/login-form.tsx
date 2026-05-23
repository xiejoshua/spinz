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
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

export function LoginForm() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginFormValues) {
    try {
      const user = await apiClient.post<SanitizedUser>("/api/v1/auth/login", values);
      setUser(user);
      router.push("/");
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          form.setError("root", { message: "Wrong email or password." });
          return;
        }
        if (error.status === 429) {
          form.setError("root", {
            message: "Too many attempts. Try again in a few minutes.",
          });
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

  const rootError = form.formState.errors.root?.message;

  return (
    <Form {...form}>
      {/* noValidate disables HTML5 native validation so RHF + Zod own the error UX. */}
      {/* Without it, type="email" intercepts submit with the browser's own tooltip. */}
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
      </form>
    </Form>
  );
}
