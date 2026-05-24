"use client";

import { AuxIcon } from "@/components/icons/aux";
import { Badge } from "@/components/ui/badge";
import type { DiaryAlbumCard, DiaryEntry } from "@/lib/diary-types";
import Link from "next/link";

type Props = {
  entry: DiaryEntry;
  album: DiaryAlbumCard | undefined;
  showOwnerControls?: boolean;
  onEdit?: (entry: DiaryEntry) => void;
  onDelete?: (entry: DiaryEntry) => void;
};

export function DiaryEntryCard({ entry, album, showOwnerControls, onEdit, onDelete }: Props) {
  const coverUrl = album?.mbid
    ? `/api/cover/250/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : (album?.cover_art_url ?? null);
  const loggedDate = new Date(entry.logged_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  return (
    <li className="flex items-start gap-3 rounded-md border bg-card px-3 py-3">
      <Link
        href={`/album/${entry.album_id}`}
        className="block shrink-0"
        aria-label={`Open ${album?.title ?? "album"}`}
      >
        {coverUrl ? (
          <img
            src={coverUrl}
            alt=""
            width={64}
            height={64}
            className="size-16 rounded bg-muted object-cover"
          />
        ) : (
          <div aria-hidden="true" className="size-16 rounded bg-muted" />
        )}
      </Link>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <Link
            href={`/album/${entry.album_id}`}
            className="truncate text-sm font-medium hover:underline"
          >
            {album?.title ?? "Unknown album"}
          </Link>
          {album?.release_year != null && (
            <span className="text-xs text-muted-foreground">{album.release_year}</span>
          )}
        </div>
        <p className="truncate text-xs text-muted-foreground">
          {album?.artist_credit ?? entry.album_id}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">{loggedDate}</span>
          {entry.rating != null && (
            <span>
              <span aria-hidden="true" className="text-foreground">
                {"★".repeat(Math.round(entry.rating))}
              </span>
              <span className="sr-only">Rated {entry.rating} of 5 stars</span>
            </span>
          )}
          {entry.auxed && (
            <Badge variant="secondary" className="h-5 px-1.5 py-0">
              <span
                aria-hidden="true"
                className="mr-1 inline-flex items-center"
                style={{ color: "var(--gold)" }}
              >
                <AuxIcon filled size={12} />
              </span>
              Aux’d
            </Badge>
          )}
          {entry.relisten && (
            <span className="text-muted-foreground" aria-label="Relisten">
              relisten
            </span>
          )}
          {entry.review_id && <span className="text-muted-foreground">· review</span>}
          {entry.visibility !== "public" && (
            <Badge variant="outline" className="h-5 px-1.5 py-0 capitalize">
              {entry.visibility}
            </Badge>
          )}
          {entry.edited_at && (
            <span className="text-muted-foreground" title={`edited ${entry.edited_at}`}>
              edited
            </span>
          )}
        </div>
        {showOwnerControls && (onEdit || onDelete) && (
          <div className="mt-2 flex gap-3 text-xs">
            {onEdit && (
              <button
                type="button"
                onClick={() => onEdit(entry)}
                className="text-muted-foreground hover:text-foreground"
              >
                Edit
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(entry)}
                className="text-muted-foreground hover:text-destructive"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
