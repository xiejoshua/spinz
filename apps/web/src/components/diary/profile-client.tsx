"use client";

import { DiaryList } from "@/components/diary/diary-list";
import { BlockReportMenu } from "@/components/social/block-report-menu";
import { FollowButton } from "@/components/social/follow-button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import type { ProfileResponse } from "@/lib/social-types";
import { useAuthStore } from "@/stores/auth";
import { useQuery } from "@tanstack/react-query";

type Props = {
  handle: string;
};

export function ProfileClient({ handle }: Props) {
  const viewer = useAuthStore((s) => s.user);

  const profileQuery = useQuery({
    queryKey: ["profile", handle] as const,
    queryFn: async () =>
      apiClient.get<ProfileResponse>(`/api/v1/users/${encodeURIComponent(handle)}`),
    staleTime: 30_000,
  });

  const profile = profileQuery.data;
  const isOwner = viewer?.handle === handle;
  const relation = profile?.relation ?? (isOwner ? "self" : "anonymous");
  const showSocialControls =
    profile != null && relation !== "self" && relation !== "anonymous" && relation !== "blocked";

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-4">
        <Avatar className="size-16">
          <AvatarFallback className="text-lg">
            {(profile?.user.display_name ?? handle).slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 space-y-1">
          <h1 className="truncate text-xl font-bold tracking-tight">
            {profile?.user.display_name ?? handle}
          </h1>
          <p className="text-sm text-muted-foreground">
            @{handle}
            {profile?.user.private_profile && (
              <Badge variant="outline" className="ml-2 h-5 px-1.5 py-0 text-[10px]">
                Private
              </Badge>
            )}
          </p>
          {profile?.user.bio && <p className="pt-1 text-sm leading-relaxed">{profile.user.bio}</p>}
          {profile && (
            <dl className="flex gap-4 pt-2 text-sm">
              <div>
                <dt className="sr-only">Followers</dt>
                <dd>
                  <span className="font-medium">{profile.counts.followers}</span>{" "}
                  <span className="text-muted-foreground">followers</span>
                </dd>
              </div>
              <div>
                <dt className="sr-only">Following</dt>
                <dd>
                  <span className="font-medium">{profile.counts.following}</span>{" "}
                  <span className="text-muted-foreground">following</span>
                </dd>
              </div>
            </dl>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {profile && (
            <FollowButton
              handle={handle}
              initialRelation={profile.relation}
              initialFollowerCount={profile.counts.followers}
              visible={showSocialControls}
            />
          )}
          {profile && (
            <BlockReportMenu
              handle={handle}
              userId={profile.user.id}
              visible={showSocialControls}
            />
          )}
        </div>
      </header>
      <DiaryList handle={handle} isOwner={isOwner} />
    </div>
  );
}
