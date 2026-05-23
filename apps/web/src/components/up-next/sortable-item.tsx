"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { BacklogItem } from "@/lib/backlog-types";
import type { DiaryAlbumCard } from "@/lib/diary-types";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, MoreVertical } from "lucide-react";
import Link from "next/link";

type Props = {
  item: BacklogItem;
  album: DiaryAlbumCard | undefined;
  onRemove: (item: BacklogItem) => void;
};

export function SortableBacklogItem({ item, album, onRemove }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  const coverUrl = album?.mbid
    ? `/api/cover/250/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : (album?.cover_art_url ?? null);

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-md border bg-card px-2 py-2"
    >
      <button
        type="button"
        aria-label={`Drag to reorder ${album?.title ?? "item"}`}
        className="touch-none p-1 text-muted-foreground hover:text-foreground"
        {...attributes}
        {...listeners}
      >
        <GripVertical aria-hidden="true" className="size-4" />
      </button>
      <Link
        href={`/album/${encodeURIComponent(item.album_id)}`}
        className="flex min-w-0 flex-1 items-center gap-3"
      >
        {coverUrl ? (
          <img
            src={coverUrl}
            alt=""
            width={48}
            height={48}
            className="size-12 shrink-0 rounded bg-muted object-cover"
          />
        ) : (
          <div aria-hidden="true" className="size-12 shrink-0 rounded bg-muted" />
        )}
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-medium">{album?.title ?? "Unknown album"}</p>
          <p className="truncate text-xs text-muted-foreground">
            {album?.artist_credit ?? item.album_id}
            {album?.release_year ? ` · ${album.release_year}` : ""}
          </p>
        </div>
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Item actions"
            className="p-1 text-muted-foreground hover:text-foreground"
          >
            <MoreVertical aria-hidden="true" className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/album/${encodeURIComponent(item.album_id)}`}>Open album</Link>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={() => onRemove(item)}
          >
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}
