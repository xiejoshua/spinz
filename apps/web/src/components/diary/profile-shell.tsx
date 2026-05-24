"use client";

import { CriticBadge } from "@/components/critic-badge";
import { BlockReportMenu } from "@/components/social/block-report-menu";
import { FollowButton } from "@/components/social/follow-button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import type { ProfileResponse } from "@/lib/social-types";
import { useAuthStore } from "@/stores/auth";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

type Tab = "diary" | "reviews" | "settings";

type Props = {
  handle: string;
  activeTab: Tab;
  children: ReactNode;
};

/**
 * Shared editorial chrome for every profile route — header + tabs +
 * gates. Sub-routes (/profile/[handle], /profile/[handle]/reviews,
 * /profile/[handle]/settings) each render this with their respective
 * activeTab + body children.
 *
 *   - Header: small-caps "PROFILE" eyebrow → Newsreader display name →
 *     mono @handle → bio → stat row above a hairline
 *   - Tab nav: Diary / Reviews always visible; Settings only for the
 *     owner (viewer.handle === profile handle)
 *   - Gates: blocked-by → "unavailable" card; private + not-following
 *     → "private" card; settings + not-owner → "not allowed" card
 */
export function ProfileShell({ handle, activeTab, children }: Props) {
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

  const blockedGate = profile != null && relation === "blocked";
  const privateGate =
    !!profile?.user.private_profile &&
    relation !== "self" &&
    relation !== "following" &&
    !blockedGate;
  const pendingRequest = privateGate && relation === "pending";
  const settingsGate = activeTab === "settings" && !isOwner;

  const displayName = profile?.user.display_name ?? handle;
  const avatarUrl = profile?.user.avatar_url ?? null;

  return (
    <div className="space-y-10">
      {/* Editorial profile header */}
      <header className="space-y-6">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Profile
        </div>

        <div className="flex items-start gap-5">
          <Avatar className="size-20 shrink-0">
            {avatarUrl ? <AvatarImage src={avatarUrl} alt="" /> : null}
            <AvatarFallback>
              <span
                className="font-serif text-[24px] font-semibold tracking-[-0.01em]"
                style={{
                  color: "var(--foreground)",
                  fontFamily: "var(--font-serif)",
                }}
              >
                {displayName.slice(0, 2).toUpperCase()}
              </span>
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 space-y-2">
            <h1
              className="flex flex-wrap items-baseline gap-3 font-serif font-semibold leading-[1.05] tracking-[-0.015em]"
              style={{
                fontSize: "clamp(28px, 4.5vw, 40px)",
                color: "var(--foreground)",
                fontFamily: "var(--font-serif)",
              }}
            >
              <span className="truncate">{displayName}</span>
              <CriticBadge isCritic={profile?.user.is_critic_seed} />
            </h1>
            <div className="flex flex-wrap items-baseline gap-2">
              <span
                className="font-mono"
                style={{ fontSize: "13px", color: "var(--muted)" }}
              >
                @{handle}
              </span>
              {profile?.user.private_profile && (
                <Badge
                  variant="outline"
                  className="h-5 px-1.5 py-0 text-[10px] uppercase"
                >
                  Private
                </Badge>
              )}
            </div>
            {profile?.user.bio && !blockedGate && (
              <p
                className="pt-2 font-sans text-[15px] leading-[1.55]"
                style={{ color: "var(--foreground)", maxWidth: "55ch" }}
              >
                {profile.user.bio}
              </p>
            )}
          </div>
          <div className="hidden shrink-0 items-center gap-2 sm:flex">
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
        </div>

        {/* Stats row + mobile social controls */}
        {profile && !blockedGate && (
          <div
            className="flex flex-wrap items-center justify-between gap-y-3 pt-4"
            style={{ borderTop: "1px solid var(--separator)" }}
          >
            <dl className="flex gap-6">
              <Stat label="Followers" value={profile.counts.followers} />
              <Stat label="Following" value={profile.counts.following} />
            </dl>
            <div className="flex items-center gap-2 sm:hidden">
              <FollowButton
                handle={handle}
                initialRelation={profile.relation}
                initialFollowerCount={profile.counts.followers}
                visible={showSocialControls}
              />
              <BlockReportMenu
                handle={handle}
                userId={profile.user.id}
                visible={showSocialControls}
              />
            </div>
          </div>
        )}
      </header>

      {blockedGate ? (
        <GateCard text="This account is unavailable." />
      ) : privateGate ? (
        <GateCard
          title="This account is private."
          text={
            pendingRequest
              ? "Follow request sent — waiting for approval."
              : "Follow this user to see their diary, reviews, and lists."
          }
        />
      ) : settingsGate ? (
        <GateCard
          title="Not your settings."
          text="Only the account owner can edit profile settings."
        />
      ) : (
        <>
          <nav
            aria-label="Profile sections"
            className="flex gap-6"
            style={{ borderBottom: "1px solid var(--separator)" }}
          >
            <TabLink
              href={`/profile/${encodeURIComponent(handle)}`}
              active={activeTab === "diary"}
              label="Diary"
            />
            <TabLink
              href={`/profile/${encodeURIComponent(handle)}/reviews`}
              active={activeTab === "reviews"}
              label="Reviews"
            />
            {isOwner && (
              <TabLink
                href={`/profile/${encodeURIComponent(handle)}/settings`}
                active={activeTab === "settings"}
                label="Settings"
              />
            )}
          </nav>
          {children}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt
        className="font-mono uppercase"
        style={{
          fontSize: "10px",
          letterSpacing: "0.15em",
          color: "var(--muted)",
        }}
      >
        {label}
      </dt>
      <dd
        className="mt-1 font-serif tabular-nums"
        style={{
          fontSize: "20px",
          fontWeight: 600,
          color: "var(--foreground)",
          fontFamily: "var(--font-serif)",
        }}
      >
        {value}
      </dd>
    </div>
  );
}

function TabLink({
  href,
  active,
  label,
}: {
  href: string;
  active: boolean;
  label: string;
}) {
  const inner = (
    <span
      className="inline-block px-1 py-3 font-sans text-[14px] font-medium"
      style={{
        color: active ? "var(--foreground)" : "var(--muted)",
        borderBottom: active
          ? "2px solid var(--foreground)"
          : "2px solid transparent",
        marginBottom: "-1px",
      }}
    >
      {label}
    </span>
  );
  return active ? inner : <Link href={href}>{inner}</Link>;
}

function GateCard({ title, text }: { title?: string; text: string }) {
  if (title) {
    return (
      <div
        className="space-y-1 rounded-md p-8 text-center"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
        }}
      >
        <p
          className="font-serif font-semibold tracking-[-0.01em]"
          style={{
            fontSize: "18px",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          {title}
        </p>
        <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
          {text}
        </p>
      </div>
    );
  }
  return (
    <p
      className="rounded-md p-8 text-center font-sans text-sm"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        color: "var(--muted)",
      }}
    >
      {text}
    </p>
  );
}
