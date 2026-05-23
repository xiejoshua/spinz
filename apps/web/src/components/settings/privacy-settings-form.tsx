"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

type Visibility = "public" | "followers" | "private";

type PrivacyState = {
  private_profile: boolean;
  default_entry_visibility: Visibility;
  default_backlog_visibility: Visibility;
  keep_backlog_after_log: boolean;
};

type ProfileResponse = {
  user: {
    private_profile: boolean;
    default_entry_visibility?: Visibility;
    default_backlog_visibility?: Visibility;
    keep_backlog_after_log?: boolean;
  };
};

const DEFAULT_STATE: PrivacyState = {
  private_profile: false,
  default_entry_visibility: "public",
  default_backlog_visibility: "private",
  keep_backlog_after_log: false,
};

const PRIVACY_QUERY_KEY = ["settings", "privacy"] as const;

export function PrivacySettingsForm() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // The /users/me/privacy endpoint is write-only (PUT). For read we lean on
  // the existing profile endpoint with the viewer's own handle — but since
  // we don't always know the handle here, we just maintain local state
  // seeded from sensible defaults; the PUT response then becomes the
  // source of truth.
  const profileQuery = useQuery({
    queryKey: PRIVACY_QUERY_KEY,
    queryFn: async () =>
      apiClient.get<ProfileResponse>("/api/v1/users/me/privacy/state").catch(() => null),
    staleTime: 30_000,
    enabled: false,
  });
  const [state, setState] = useState<PrivacyState>(DEFAULT_STATE);
  useEffect(() => {
    const u = profileQuery.data?.user;
    if (!u) return;
    setState({
      private_profile: u.private_profile,
      default_entry_visibility: u.default_entry_visibility ?? "public",
      default_backlog_visibility: u.default_backlog_visibility ?? "private",
      keep_backlog_after_log: u.keep_backlog_after_log ?? false,
    });
  }, [profileQuery.data]);

  const mutation = useMutation({
    mutationFn: async (next: PrivacyState) =>
      apiClient.put<PrivacyState & { private_profile: boolean }>("/api/v1/users/me/privacy", next),
    onSuccess: (data) => {
      setState(data);
      toast({ title: "Privacy updated" });
      capture("privacy.updated", data as unknown as Record<string, unknown>);
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast({
          title: "Could not update privacy",
          description: error.statusText,
          variant: "destructive",
        });
      }
    },
  });

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate(state);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <fieldset className="space-y-3 rounded-md border p-4">
        <legend className="px-1 text-sm font-medium">Default visibility</legend>
        <div className="space-y-2">
          <Label htmlFor="entry-visibility">New diary entries</Label>
          <Select
            value={state.default_entry_visibility}
            onValueChange={(value) =>
              setState((s) => ({ ...s, default_entry_visibility: value as Visibility }))
            }
          >
            <SelectTrigger id="entry-visibility" className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="public">Public</SelectItem>
              <SelectItem value="followers">Followers only</SelectItem>
              <SelectItem value="private">Private (only me)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="backlog-visibility">Up Next backlog</Label>
          <Select
            value={state.default_backlog_visibility}
            onValueChange={(value) =>
              setState((s) => ({ ...s, default_backlog_visibility: value as Visibility }))
            }
          >
            <SelectTrigger id="backlog-visibility" className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="public">Public</SelectItem>
              <SelectItem value="followers">Followers only</SelectItem>
              <SelectItem value="private">Private (only me)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-md border p-4">
        <legend className="px-1 text-sm font-medium">Profile</legend>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="private-profile" className="font-medium">
              Private profile
            </Label>
            <p className="text-xs text-muted-foreground">
              Your diary, reviews, and lists won&rsquo;t be visible to anyone who doesn&rsquo;t
              follow you. New follow attempts create pending requests you can approve or decline.
            </p>
          </div>
          <Switch
            id="private-profile"
            checked={state.private_profile}
            onCheckedChange={(checked) => setState((s) => ({ ...s, private_profile: checked }))}
          />
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-md border p-4">
        <legend className="px-1 text-sm font-medium">Up Next behavior</legend>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="keep-backlog" className="font-medium">
              Keep items in Up Next after logging
            </Label>
            <p className="text-xs text-muted-foreground">
              When off, logging an album removes it from your Up Next automatically.
            </p>
          </div>
          <Switch
            id="keep-backlog"
            checked={state.keep_backlog_after_log}
            onCheckedChange={(checked) =>
              setState((s) => ({ ...s, keep_backlog_after_log: checked }))
            }
          />
        </div>
      </fieldset>

      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving…" : "Save privacy settings"}
      </Button>
    </form>
  );
}
