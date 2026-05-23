"use client";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useUiStore } from "@/stores/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AlbumSearch } from "./album-search";
import { AuxToggle } from "./aux-toggle";
import { RatingWidget } from "./rating-widget";
import { ReviewEditor } from "./review-editor";

type Visibility = "public" | "followers" | "private";

type LogEntryResponse = {
  id: string;
  album_id: string;
  logged_at: string;
  rating: number | null;
  auxed: boolean;
  review_id: string | null;
  visibility: Visibility;
  relisten: boolean;
  created_at: string;
  was_created: boolean;
};

type EditEntryResponse = {
  id: string;
  album_id: string;
  rating: number | null;
  auxed: boolean;
  visibility: Visibility;
  edited_at: string | null;
};

export function LogSheet() {
  const open = useUiStore((s) => s.logSheetOpen);
  const seed = useUiStore((s) => s.logSheetSeed);
  const close = useUiStore((s) => s.closeLogSheet);
  const setSeed = useUiStore((s) => s.openLogSheet);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const isEdit = seed?.edit != null;

  const [rating, setRating] = useState<number | null>(null);
  const [auxed, setAuxed] = useState(false);
  const [reviewBody, setReviewBody] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("public");
  const [submitting, setSubmitting] = useState(false);
  const [openedAt, setOpenedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!open) {
      setRating(null);
      setAuxed(false);
      setReviewBody("");
      setVisibility("public");
      setOpenedAt(null);
      setSubmitting(false);
      return;
    }
    setOpenedAt(performance.now());
    if (seed?.edit) {
      setRating(seed.edit.rating);
      setAuxed(seed.edit.auxed);
      setVisibility(seed.edit.visibility);
      // Review body is intentionally not pre-filled — review CRUD lands
      // in §8 (T085-T087); for now, edit covers rating/aux/visibility
      // and leaves any attached review unchanged.
      setReviewBody("");
    }
  }, [open, seed]);

  async function handleSubmit() {
    if (!seed || submitting) return;
    setSubmitting(true);
    const startedCommitAt = performance.now();
    try {
      if (seed.edit) {
        const body: Record<string, unknown> = {
          rating,
          auxed,
          visibility,
        };
        const updated = await apiClient.patch<EditEntryResponse>(
          `/api/v1/diary/entries/${encodeURIComponent(seed.edit.entry_id)}`,
          body
        );
        const commitMs = performance.now() - startedCommitAt;
        capture("log.edit", {
          commit_ms: commitMs,
          entry_id: updated.id,
          has_rating: rating != null,
        });
        toast({ title: "Updated", description: `Updated — ${seed.title}` });
        await queryClient.invalidateQueries({ queryKey: ["diary"] });
        await queryClient.invalidateQueries({ queryKey: ["album"] });
        close();
        return;
      }

      const body: Record<string, unknown> = {
        album_id: seed.album_id,
        auxed,
        visibility,
      };
      if (rating != null) body.rating = rating;
      if (reviewBody.trim().length > 0) body.review_body = reviewBody.trim();

      const entry = await apiClient.post<LogEntryResponse>("/api/v1/diary/entries", body);

      const totalMs = openedAt != null ? performance.now() - openedAt : null;
      const commitMs = performance.now() - startedCommitAt;
      capture("log.commit", {
        duration_ms: totalMs,
        commit_ms: commitMs,
        has_rating: rating != null,
        has_review: reviewBody.trim().length > 0,
        auxed,
        relisten: entry.relisten,
        was_created: entry.was_created,
        source: "manual",
      });

      toast({
        title: entry.was_created ? "Logged" : "Already logged",
        description: entry.relisten
          ? `Relisten captured — ${seed.title}`
          : `Logged — ${seed.title}`,
      });
      await queryClient.invalidateQueries({ queryKey: ["diary"] });
      await queryClient.invalidateQueries({ queryKey: ["album"] });
      close();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.status === 422
            ? "Invalid rating or review."
            : error.status === 404
              ? isEdit
                ? "Entry not found."
                : "That album isn’t in the catalog. Try a different search."
              : error.status === 403
                ? "You can only edit your own entries."
                : `Log failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: isEdit ? "Couldn’t update" : "Couldn’t log", description: message });
      setSubmitting(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={(value) => (value ? null : close())}>
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl sm:mx-auto">
        <SheetHeader className="text-left">
          <SheetTitle>{isEdit ? "Edit diary entry" : "Log an album"}</SheetTitle>
        </SheetHeader>
        {seed ? (
          <SeedHeader seed={seed} onClear={isEdit ? undefined : () => setSeed()} />
        ) : (
          <AlbumSearch onPick={(picked) => setSeed(picked)} />
        )}
        {seed && (
          <div className="mt-4 space-y-5">
            <section aria-labelledby="rating-heading" className="space-y-2">
              <h3 id="rating-heading" className="text-sm font-medium">
                Your rating
              </h3>
              <RatingWidget value={rating} onChange={setRating} />
            </section>
            <section className="flex flex-wrap items-center gap-3">
              <AuxToggle value={auxed} onChange={setAuxed} />
              <Select value={visibility} onValueChange={(v) => setVisibility(v as Visibility)}>
                <SelectTrigger className="h-9 w-auto px-3 text-sm" aria-label="Visibility">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="public">Public</SelectItem>
                  <SelectItem value="followers">Followers only</SelectItem>
                  <SelectItem value="private">Private</SelectItem>
                </SelectContent>
              </Select>
            </section>
            {!isEdit && <ReviewEditor value={reviewBody} onChange={setReviewBody} />}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={close} disabled={submitting}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? (isEdit ? "Updating…" : "Logging…") : isEdit ? "Save" : "Log"}
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function SeedHeader({
  seed,
  onClear,
}: {
  seed: NonNullable<ReturnType<typeof useUiStore.getState>["logSheetSeed"]>;
  onClear?: () => void;
}) {
  const coverUrl = seed.mbid
    ? `/api/cover/250/${seed.mbid}${seed.cover_art_url ? `?fallback=${encodeURIComponent(seed.cover_art_url)}` : ""}`
    : seed.cover_art_url;
  return (
    <div className="mt-4 flex items-start gap-3 rounded-md border p-3">
      {coverUrl ? (
        <img
          src={coverUrl}
          alt=""
          width={56}
          height={56}
          className="size-14 shrink-0 rounded bg-muted object-cover"
        />
      ) : (
        <div aria-hidden="true" className="size-14 shrink-0 rounded bg-muted" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{seed.title}</p>
        <p className="truncate text-xs text-muted-foreground">{seed.artist_credit}</p>
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
        >
          Change
        </button>
      )}
    </div>
  );
}
