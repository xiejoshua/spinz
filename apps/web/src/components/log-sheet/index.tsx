"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
      setReviewBody("");
    }
  }, [open, seed]);

  async function handleSubmit() {
    if (!seed || submitting) return;
    setSubmitting(true);
    const startedCommitAt = performance.now();
    try {
      if (seed.edit) {
        const body: Record<string, unknown> = { rating, auxed, visibility };
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
                : "That album isn't in the catalog. Try a different search."
              : error.status === 403
                ? "You can only edit your own entries."
                : `Log failed (${error.status}).`
          : "Could not reach the server.";
      toast({
        title: isEdit ? "Couldn't update" : "Couldn't log",
        description: message,
      });
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? null : close())}>
      <DialogContent
        className="max-h-[85vh] w-[calc(100vw-2rem)] max-w-[560px] overflow-y-auto"
        style={{ background: "var(--surface)" }}
      >
        <div className="px-8 py-10 sm:px-10 sm:py-12">
          {/* Editorial title row */}
          <header className="mb-6 flex items-baseline justify-between gap-4">
            <div>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.18em",
                  color: "var(--muted)",
                }}
              >
                {isEdit ? "Edit" : "Log"}
              </div>
              <h2
                className="mt-1 font-serif font-semibold leading-[1.05] tracking-[-0.015em]"
                style={{
                  fontSize: "28px",
                  color: "var(--foreground)",
                  fontFamily: "var(--font-serif)",
                }}
              >
                {isEdit ? "Edit your log." : "Log an album."}
              </h2>
            </div>
          </header>

          {/* Body */}
          {seed ? (
            <SeedHeader seed={seed} onClear={isEdit ? undefined : () => setSeed()} />
          ) : (
            <AlbumSearch onPick={(picked) => setSeed(picked)} />
          )}

          {seed && (
            <div className="mt-8 space-y-6">
              <Row label="Rate" hint="tap a star — drag for half-stars">
                <RatingWidget value={rating} onChange={setRating} />
              </Row>

              <Row label="Aux" hint="your standout signal">
                <AuxToggle value={auxed} onChange={setAuxed} />
              </Row>

              <Row label="Visibility">
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
              </Row>

              {!isEdit && (
                <Row label="Review" hint="optional">
                  <ReviewEditor value={reviewBody} onChange={setReviewBody} />
                </Row>
              )}

              <div
                className="flex justify-end gap-3 pt-4"
                style={{ borderTop: "1px solid var(--separator)" }}
              >
                <Button variant="ghost" onClick={close} disabled={submitting}>
                  Cancel
                </Button>
                <Button onClick={handleSubmit} disabled={submitting}>
                  {submitting ? (isEdit ? "Updating…" : "Logging…") : isEdit ? "Save" : "Log →"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 pb-5"
      style={{ borderBottom: "1px solid var(--separator)" }}
    >
      <div className="min-w-[120px]">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.15em",
            color: "var(--muted)",
          }}
        >
          {label}
        </div>
        {hint && (
          <div
            className="mt-1 font-sans text-[12px] leading-tight"
            style={{ color: "var(--muted)" }}
          >
            {hint}
          </div>
        )}
      </div>
      <div className="flex-1">{children}</div>
    </div>
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
    <div
      className="flex items-center gap-4 rounded-md p-4"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
      }}
    >
      {coverUrl ? (
        <img
          src={coverUrl}
          alt=""
          width={64}
          height={64}
          className="size-16 shrink-0 rounded object-cover"
          style={{ background: "var(--surface-secondary)" }}
        />
      ) : (
        <div
          aria-hidden="true"
          className="size-16 shrink-0 rounded"
          style={{
            background:
              "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
          }}
        />
      )}
      <div className="min-w-0 flex-1">
        <p
          className="truncate font-serif text-[18px] font-semibold tracking-[-0.005em]"
          style={{
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          {seed.title}
        </p>
        <p className="mt-0.5 truncate font-sans text-[13px]" style={{ color: "var(--muted)" }}>
          {seed.artist_credit}
        </p>
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="shrink-0 cursor-pointer font-mono uppercase tracking-[0.12em] hover:underline"
          style={{
            fontSize: "10px",
            color: "var(--muted)",
          }}
        >
          Change
        </button>
      )}
    </div>
  );
}
