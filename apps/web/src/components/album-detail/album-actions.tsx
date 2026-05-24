"use client";

import { ReportWrongAlbum } from "@/components/album-detail/report-wrong";
import { UpNextButton } from "@/components/album-detail/up-next-button";
import { AuxIcon } from "@/components/icons/aux";
import { Button } from "@/components/ui/button";
import type { AlbumPayload, DiaryRow } from "@/lib/album-types";
import { useUiStore } from "@/stores/ui";
import { Plus } from "lucide-react";

type Props = {
  album: AlbumPayload;
  myEntry: DiaryRow | null;
};

export function AlbumActions({ album, myEntry }: Props) {
  const openLogSheet = useUiStore((s) => s.openLogSheet);

  function startLog() {
    openLogSheet({
      album_id: album.id,
      mbid: album.mbid,
      title: album.title,
      artist_credit: album.artist_credit,
      cover_art_url: album.cover_art_url,
    });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={startLog}>
        <Plus className="mr-1 size-4" aria-hidden="true" />
        {myEntry ? "Log again" : "Log"}
      </Button>
      <UpNextButton albumId={album.id} />
      {myEntry?.rating != null && (
        <span className="self-center text-sm text-muted-foreground">
          You rated this <span className="text-foreground">{myEntry.rating}★</span>
          {myEntry.auxed && (
            <>
              {" "}
              ·{" "}
              <span
                aria-hidden="true"
                className="inline-flex items-center align-text-bottom"
                style={{ color: "var(--gold)" }}
              >
                <AuxIcon filled size={14} />
              </span>{" "}
              Aux’d
            </>
          )}
        </span>
      )}
      <div className="ml-auto">
        <ReportWrongAlbum albumId={album.id} albumTitle={album.title} />
      </div>
    </div>
  );
}
