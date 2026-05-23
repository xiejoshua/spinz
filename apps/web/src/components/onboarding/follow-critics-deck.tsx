"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { stashOnboardingFollows } from "@/lib/analytics";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { markFollow } from "@/lib/push-subscription";
import type {
  FollowMutationResponse,
  OnboardingCard as OnboardingCardType,
  OnboardingCardsResponse,
} from "@/lib/social-types";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const QUERY_KEY = ["onboarding-cards"] as const;
const MIN_REQUIRED = 1; // task spec: minimum 1 to advance; copy still nudges 3

export function FollowCriticsDeck() {
  const router = useRouter();
  const { toast } = useToast();
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [submitting, setSubmitting] = useState(false);

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => apiClient.get<OnboardingCardsResponse>("/api/v1/onboarding/cards"),
    staleTime: 60_000,
  });

  // Seed the selection from the server-side pre_checked flag on first load.
  // Keyed on data identity, not card-array contents, so re-renders during
  // the user's toggling don't overwrite their choices.
  useEffect(() => {
    if (!query.data) return;
    setSelected((cur) => {
      // First load: cur is empty, we seed from pre_checked.
      // Re-load after refetch: keep whatever the user already toggled.
      if (cur.size > 0) return cur;
      return new Set(query.data.cards.filter((c) => c.pre_checked).map((c) => c.user.id));
    });
  }, [query.data]);

  const cards = useMemo(() => query.data?.cards ?? [], [query.data]);

  function toggle(card: OnboardingCardType) {
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(card.user.id)) {
        next.delete(card.user.id);
      } else {
        next.add(card.user.id);
      }
      return next;
    });
  }

  async function handleContinue() {
    if (submitting) return;
    if (selected.size < MIN_REQUIRED) {
      toast({
        title: "Pick at least one critic",
        description: "Your feed needs someone to fill it.",
      });
      return;
    }
    setSubmitting(true);
    const targets = cards.filter((c) => selected.has(c.user.id));
    const results = await Promise.allSettled(
      targets.map((card) =>
        apiClient.post<FollowMutationResponse>(
          `/api/v1/users/${encodeURIComponent(card.user.handle)}/follow`,
          { source: card.source }
        )
      )
    );

    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failures = results
      .map((r, i) => ({ result: r, card: targets[i] }))
      .filter((x) => x.result.status === "rejected");

    // T141 — record successful follows so the push prompt can fire once
    // the threshold is crossed.
    for (let i = 0; i < succeeded; i++) {
      markFollow();
    }

    const succeededCards = targets.filter((_card, i) => results[i].status === "fulfilled");
    const criticSeedKeptPct =
      succeededCards.length > 0
        ? Math.round(
            (succeededCards.filter((c) => c.source === "onboarding_preselected").length /
              succeededCards.length) *
              100
          )
        : 0;
    capture("onboarding.follow_selected", {
      selected_count: targets.length,
      succeeded_count: succeeded,
      failed_count: failures.length,
      critic_seed_kept_pct: criticSeedKeptPct,
    });
    // Stash for the completion event on step-3. We use the *succeeded*
    // counts, not the optimistic selection, so a partial network
    // failure doesn't inflate the funnel.
    stashOnboardingFollows({
      follows_count: succeededCards.length,
      critic_seed_kept_pct: criticSeedKeptPct,
    });

    if (failures.length > 0) {
      const sample = failures[0];
      const message =
        sample.result.status === "rejected" && sample.result.reason instanceof ApiError
          ? `${sample.card.user.handle} failed (${sample.result.reason.status}).`
          : `${sample.card.user.handle} could not be followed.`;
      toast({ title: "Some follows failed", description: message });
      setSubmitting(false);
      if (succeeded === 0) {
        return; // total failure — let the user retry without bouncing them forward
      }
    }
    router.push("/onboarding/step-3");
  }

  if (query.isLoading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Loading critics…</p>;
  }
  if (query.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">Could not load critics.</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void query.refetch();
          }}
        >
          Retry
        </Button>
      </div>
    );
  }
  if (cards.length === 0) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          No critics seeded yet. You can skip this step and find people to follow later.
        </p>
        <Button asChild variant="outline">
          {/* Skip path: jump straight to step-3 so the user isn't stuck. */}
          <a href="/onboarding/step-3">Skip for now</a>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {cards.map((card) => {
          const isSelected = selected.has(card.user.id);
          return (
            <li key={card.user.id}>
              <button
                type="button"
                onClick={() => {
                  toggle(card);
                }}
                aria-pressed={isSelected}
                className={cn(
                  "flex w-full items-start gap-3 rounded-md border bg-card p-3 text-left transition-colors",
                  isSelected
                    ? "border-foreground ring-1 ring-foreground"
                    : "hover:border-muted-foreground/40"
                )}
              >
                <Avatar className="size-12 shrink-0">
                  {card.user.avatar_url ? <AvatarImage src={card.user.avatar_url} alt="" /> : null}
                  <AvatarFallback>{card.user.handle.slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="truncate text-sm font-medium leading-tight">
                    {card.user.display_name}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">@{card.user.handle}</p>
                  {card.user.bio ? (
                    <p className="line-clamp-2 pt-1 text-xs text-muted-foreground">
                      {card.user.bio}
                    </p>
                  ) : null}
                </div>
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-1 flex size-5 shrink-0 items-center justify-center rounded-full border text-xs",
                    isSelected ? "border-foreground bg-foreground text-background" : "border-border"
                  )}
                >
                  {isSelected ? "✓" : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="flex items-center justify-between gap-3 pt-2">
        <p className="text-xs text-muted-foreground">
          {selected.size} selected · pick at least {MIN_REQUIRED}
        </p>
        <Button
          type="button"
          disabled={submitting || selected.size < MIN_REQUIRED}
          onClick={() => {
            void handleContinue();
          }}
        >
          {submitting ? "Following…" : "Continue"}
        </Button>
      </div>
    </div>
  );
}
