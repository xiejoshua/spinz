"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { setApiFormErrors, zodResolver } from "@/lib/forms";
import { capture } from "@/lib/posthog";
import { useAuthStore } from "@/stores/auth";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const HANDLE_MIN = 3;
const HANDLE_MAX = 30;
const DISPLAY_NAME_MAX = 30;
const BIO_MAX = 280;
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
const AVATAR_ACCEPT = "image/jpeg,image/png,image/webp";

const profileSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(1, "Display name cannot be empty")
    .max(DISPLAY_NAME_MAX, `Display name must be ${DISPLAY_NAME_MAX} characters or fewer`),
  bio: z.string().max(BIO_MAX, `Bio must be ${BIO_MAX} characters or fewer`),
  handle: z
    .string()
    .trim()
    .min(HANDLE_MIN, `Handle must be at least ${HANDLE_MIN} characters`)
    .max(HANDLE_MAX, `Handle must be at most ${HANDLE_MAX} characters`)
    .regex(/^[a-z0-9_]+$/, "Handle can only contain lowercase letters, digits, and underscores"),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

type PatchMeResponse = {
  id: string;
  handle: string;
  display_name: string;
  bio: string;
  avatar_url: string | null;
};

type HandleChangeResponse = {
  handle: string;
  handle_changed_at: string | null;
};

type AvatarUploadResponse = {
  avatar_url: string;
  sizes: Record<string, string>;
};

export function EditProfileForm() {
  const viewer = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      display_name: viewer?.display_name ?? "",
      bio: "",
      handle: viewer?.handle ?? "",
    },
  });

  // Keep the form synced when the auth store hydrates after first render.
  // biome-ignore lint/correctness/useExhaustiveDependencies: only rehydrate when the viewer identity changes
  useEffect(() => {
    if (viewer) {
      form.reset({
        display_name: viewer.display_name,
        bio: form.getValues("bio"),
        handle: viewer.handle,
      });
    }
  }, [viewer?.id, viewer?.handle, viewer?.display_name]);

  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);

  const avatarMutation = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/v1/users/me/avatar", {
        method: "POST",
        body,
        credentials: "include",
      });
      if (!response.ok) {
        let detail: unknown;
        try {
          detail = await response.json();
        } catch {
          // ignore non-json bodies
        }
        throw new ApiError(response.status, response.statusText, detail);
      }
      return (await response.json()) as AvatarUploadResponse;
    },
    onSuccess: (data) => {
      toast({ title: "Avatar updated" });
      capture("profile.avatar_uploaded");
      setAvatarPreview(data.avatar_url);
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const detail = (error.detail as { detail?: { message?: string } } | undefined)?.detail;
        toast({
          title: "Avatar upload failed",
          description: detail?.message ?? error.statusText,
          variant: "destructive",
        });
      } else {
        toast({
          title: "Avatar upload failed",
          description: "Please try again.",
          variant: "destructive",
        });
      }
    },
  });

  const profileMutation = useMutation({
    mutationFn: async (values: { display_name: string; bio: string }) =>
      apiClient.patch<PatchMeResponse>("/api/v1/users/me", values),
    onSuccess: (data) => {
      if (viewer) {
        setUser({ ...viewer, display_name: data.display_name });
      }
      toast({ title: "Profile saved" });
      capture("profile.updated");
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const handled = setApiFormErrors(form, error.detail as { detail?: unknown } | undefined);
        if (!handled) {
          toast({
            title: "Could not save profile",
            description: error.statusText,
            variant: "destructive",
          });
        }
      }
    },
  });

  const handleMutation = useMutation({
    mutationFn: async (newHandle: string) =>
      apiClient.post<HandleChangeResponse>("/api/v1/users/me/handle", {
        new_handle: newHandle,
      }),
    onSuccess: (data) => {
      if (viewer) {
        setUser({ ...viewer, handle: data.handle });
      }
      toast({ title: "Handle updated" });
      capture("profile.handle_changed", { new_handle: data.handle });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const payload = error.detail as
          | { detail?: { error?: string; message?: string; retry_after_days?: number } }
          | undefined;
        const detail = payload?.detail;
        if (error.status === 429 && detail?.retry_after_days != null) {
          form.setError("handle", {
            message: `You can change your handle again in ${detail.retry_after_days} days.`,
          });
          return;
        }
        if (!setApiFormErrors(form, payload)) {
          toast({
            title: "Could not update handle",
            description: detail?.message ?? error.statusText,
            variant: "destructive",
          });
        }
      }
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const profileChanged =
      values.display_name !== (viewer?.display_name ?? "") || values.bio !== "";
    const handleChanged = viewer != null && values.handle !== viewer.handle;
    try {
      if (profileChanged) {
        await profileMutation.mutateAsync({
          display_name: values.display_name,
          bio: values.bio ?? "",
        });
      }
      if (handleChanged) {
        await handleMutation.mutateAsync(values.handle);
      }
      if (!profileChanged && !handleChanged) {
        toast({ title: "Nothing to save" });
      }
    } catch {
      // errors surfaced via the mutation handlers above
    }
  });

  function onAvatarChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > AVATAR_MAX_BYTES) {
      toast({
        title: "Avatar too large",
        description: "Choose an image under 5 MB.",
        variant: "destructive",
      });
      return;
    }
    avatarMutation.mutate(file);
  }

  const handleFallback = viewer?.handle?.slice(0, 2).toUpperCase() ?? "AU";

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-6"
      aria-busy={profileMutation.isPending || handleMutation.isPending}
    >
      <section className="flex items-center gap-4">
        <Avatar className="size-16">
          {avatarPreview ? <AvatarImage src={avatarPreview} alt="" /> : null}
          <AvatarFallback>{handleFallback}</AvatarFallback>
        </Avatar>
        <div className="space-y-2">
          <Label htmlFor="avatar-input" className="text-sm font-medium">
            Avatar
          </Label>
          <input
            id="avatar-input"
            type="file"
            accept={AVATAR_ACCEPT}
            onChange={onAvatarChange}
            className="block text-sm"
          />
          <p className="text-xs text-muted-foreground">JPEG, PNG, or WebP. Max 5 MB.</p>
        </div>
      </section>

      <div className="space-y-2">
        <Label htmlFor="display_name">Display name</Label>
        <Input
          id="display_name"
          {...form.register("display_name")}
          maxLength={DISPLAY_NAME_MAX}
          aria-invalid={form.formState.errors.display_name != null}
        />
        {form.formState.errors.display_name && (
          <p className="text-xs text-destructive">{form.formState.errors.display_name.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="bio">Bio</Label>
        <textarea
          id="bio"
          {...form.register("bio")}
          maxLength={BIO_MAX}
          className="flex min-h-[80px] w-full rounded-md border bg-background px-3 py-2 text-sm shadow-sm"
        />
        {form.formState.errors.bio && (
          <p className="text-xs text-destructive">{form.formState.errors.bio.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="handle">Handle</Label>
        <Input
          id="handle"
          {...form.register("handle")}
          maxLength={HANDLE_MAX}
          aria-invalid={form.formState.errors.handle != null}
        />
        {form.formState.errors.handle && (
          <p className="text-xs text-destructive">{form.formState.errors.handle.message}</p>
        )}
        <p className="text-xs text-muted-foreground">
          Your unique username on auxd. You can change it once every 30 days.
        </p>
      </div>

      {form.formState.errors.root && (
        <p className="text-sm text-destructive">{form.formState.errors.root.message}</p>
      )}

      <Button type="submit" disabled={profileMutation.isPending || handleMutation.isPending}>
        {profileMutation.isPending || handleMutation.isPending ? "Saving…" : "Save changes"}
      </Button>
    </form>
  );
}
