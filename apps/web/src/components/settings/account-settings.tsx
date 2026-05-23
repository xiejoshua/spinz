"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { setApiFormErrors, zodResolver } from "@/lib/forms";
import { capture } from "@/lib/posthog";
import { useAuthStore } from "@/stores/auth";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

const emailSchema = z.object({
  new_email: z.string().email("Enter a valid email"),
  current_password: z.string().min(1, "Enter your current password"),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z
      .string()
      .min(12, "Password must be at least 12 characters")
      .max(128, "Password must be at most 128 characters"),
    confirm_new_password: z.string().min(1, "Confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_new_password, {
    message: "Passwords do not match",
    path: ["confirm_new_password"],
  });

type EmailFormValues = z.infer<typeof emailSchema>;
type PasswordFormValues = z.infer<typeof passwordSchema>;

export function AccountSettings() {
  const router = useRouter();
  const { toast } = useToast();
  const viewer = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const clearUser = useAuthStore((s) => s.clear);

  const emailForm = useForm<EmailFormValues>({
    resolver: zodResolver(emailSchema),
    defaultValues: { new_email: "", current_password: "" },
  });

  const passwordForm = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_new_password: "" },
  });

  const emailMutation = useMutation({
    mutationFn: async (values: EmailFormValues) =>
      apiClient.post<{ email: string; session_version: number }>("/api/v1/users/me/email", values),
    onSuccess: (data) => {
      if (viewer) setUser({ ...viewer, email: data.email });
      toast({ title: "Email updated" });
      capture("email.changed");
      emailForm.reset({ new_email: "", current_password: "" });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const detail = error.detail as { detail?: unknown } | undefined;
        if (!setApiFormErrors(emailForm, detail)) {
          const message =
            (detail?.detail as { message?: string } | undefined)?.message ?? error.statusText;
          toast({ title: "Could not change email", description: message, variant: "destructive" });
        }
      }
    },
  });

  const passwordMutation = useMutation({
    mutationFn: async (values: PasswordFormValues) =>
      apiClient.post<{ session_version: number }>("/api/v1/users/me/password", {
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    onSuccess: () => {
      toast({ title: "Password updated" });
      capture("password.changed");
      passwordForm.reset({
        current_password: "",
        new_password: "",
        confirm_new_password: "",
      });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const detail = error.detail as { detail?: unknown } | undefined;
        if (!setApiFormErrors(passwordForm, detail)) {
          const message =
            (detail?.detail as { message?: string } | undefined)?.message ?? error.statusText;
          toast({
            title: "Could not change password",
            description: message,
            variant: "destructive",
          });
        }
      }
    },
  });

  const logoutAllMutation = useMutation({
    mutationFn: async () => apiClient.post("/api/v1/auth/logout-all-devices"),
    onSuccess: () => {
      clearUser();
      toast({ title: "Signed out everywhere" });
      router.push("/login");
    },
    onError: (error) => {
      toast({
        title: "Could not sign out",
        description: error instanceof ApiError ? error.statusText : "Try again later.",
        variant: "destructive",
      });
    },
  });

  return (
    <div className="space-y-8">
      <form
        onSubmit={emailForm.handleSubmit((values) => emailMutation.mutate(values))}
        className="space-y-3 rounded-md border p-4"
        aria-busy={emailMutation.isPending}
      >
        <h3 className="text-sm font-medium">Change email</h3>
        <p className="text-xs text-muted-foreground">Current: {viewer?.email ?? "—"}</p>
        <div className="space-y-2">
          <Label htmlFor="new_email">New email</Label>
          <Input
            id="new_email"
            type="email"
            autoComplete="email"
            {...emailForm.register("new_email")}
            aria-invalid={emailForm.formState.errors.new_email != null}
          />
          {emailForm.formState.errors.new_email && (
            <p className="text-xs text-destructive">
              {emailForm.formState.errors.new_email.message}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="current_password_email">Current password</Label>
          <Input
            id="current_password_email"
            type="password"
            autoComplete="current-password"
            {...emailForm.register("current_password")}
            aria-invalid={emailForm.formState.errors.current_password != null}
          />
          {emailForm.formState.errors.current_password && (
            <p className="text-xs text-destructive">
              {emailForm.formState.errors.current_password.message}
            </p>
          )}
        </div>
        {emailForm.formState.errors.root && (
          <p className="text-sm text-destructive">{emailForm.formState.errors.root.message}</p>
        )}
        <Button type="submit" disabled={emailMutation.isPending}>
          {emailMutation.isPending ? "Saving…" : "Update email"}
        </Button>
      </form>

      <form
        onSubmit={passwordForm.handleSubmit((values) => passwordMutation.mutate(values))}
        className="space-y-3 rounded-md border p-4"
        aria-busy={passwordMutation.isPending}
      >
        <h3 className="text-sm font-medium">Change password</h3>
        <div className="space-y-2">
          <Label htmlFor="current_password_pw">Current password</Label>
          <Input
            id="current_password_pw"
            type="password"
            autoComplete="current-password"
            {...passwordForm.register("current_password")}
            aria-invalid={passwordForm.formState.errors.current_password != null}
          />
          {passwordForm.formState.errors.current_password && (
            <p className="text-xs text-destructive">
              {passwordForm.formState.errors.current_password.message}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="new_password">New password</Label>
          <Input
            id="new_password"
            type="password"
            autoComplete="new-password"
            {...passwordForm.register("new_password")}
            aria-invalid={passwordForm.formState.errors.new_password != null}
          />
          {passwordForm.formState.errors.new_password && (
            <p className="text-xs text-destructive">
              {passwordForm.formState.errors.new_password.message}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm_new_password">Confirm new password</Label>
          <Input
            id="confirm_new_password"
            type="password"
            autoComplete="new-password"
            {...passwordForm.register("confirm_new_password")}
            aria-invalid={passwordForm.formState.errors.confirm_new_password != null}
          />
          {passwordForm.formState.errors.confirm_new_password && (
            <p className="text-xs text-destructive">
              {passwordForm.formState.errors.confirm_new_password.message}
            </p>
          )}
        </div>
        {passwordForm.formState.errors.root && (
          <p className="text-sm text-destructive">{passwordForm.formState.errors.root.message}</p>
        )}
        <Button type="submit" disabled={passwordMutation.isPending}>
          {passwordMutation.isPending ? "Saving…" : "Update password"}
        </Button>
      </form>

      <section className="space-y-3 rounded-md border p-4">
        <h3 className="text-sm font-medium">Sign out of all devices</h3>
        <p className="text-xs text-muted-foreground">
          Invalidates every active session, including the current one. You&rsquo;ll be asked to sign
          in again on this device.
        </p>
        <Dialog>
          <DialogTrigger asChild>
            <Button type="button" variant="outline">
              Sign out everywhere
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Sign out of all devices?</DialogTitle>
              <DialogDescription>
                You&rsquo;ll be signed out here too and will need to log in again.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="destructive"
                onClick={() => logoutAllMutation.mutate()}
                disabled={logoutAllMutation.isPending}
              >
                {logoutAllMutation.isPending ? "Signing out…" : "Sign out everywhere"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>
    </div>
  );
}
