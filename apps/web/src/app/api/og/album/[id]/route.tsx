import { ALBUM_TITLE_MAX, backendUrl, truncate } from "@/app/api/og/helpers";
import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

/**
 * Share-card OG image generator for ``/album/[id]`` (T168).
 *
 * Renders a 1200×630 PNG via Vercel's ``next/og`` ImageResponse, then
 * caches the result at the CDN with a one-year ``immutable``
 * Cache-Control. Backend fetches use ``API_BACKEND_URL`` (server-only)
 * so the route bypasses the Next rewrites layer.
 *
 * On a backend 404 we render a generic auxd-branded fallback rather
 * than letting the call fail — social crawlers fetch OG images at
 * unpredictable times and a 500 here would suppress the embed.
 */

export const runtime = "nodejs";

const WIDTH = 1200;
const HEIGHT = 630;
const CACHE_HEADER = "public, max-age=31536000, s-maxage=31536000, immutable";

type AlbumPayload = {
  album: {
    id: string;
    title: string;
    artist_credit: string;
    cover_art_url?: string | null;
    release_year?: number | null;
  };
  aggregate: {
    avg_rating: number;
    rating_count: number;
  };
};

async function loadAlbum(id: string): Promise<AlbumPayload | null> {
  try {
    const response = await fetch(backendUrl(`/api/v1/albums/${encodeURIComponent(id)}`), {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as AlbumPayload;
  } catch {
    return null;
  }
}

function FallbackCard() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        background: "#0b0b10",
        color: "white",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ fontSize: 96, fontWeight: 700 }}>auxd</div>
      <div style={{ fontSize: 32, color: "#9aa0aa", marginTop: 12 }}>a music diary</div>
    </div>
  );
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const { id } = await params;
  const data = await loadAlbum(id);

  if (!data) {
    return new ImageResponse(<FallbackCard />, {
      width: WIDTH,
      height: HEIGHT,
      headers: { "Cache-Control": "public, max-age=300, s-maxage=300" },
    });
  }

  const { album, aggregate } = data;
  const title = truncate(album.title, ALBUM_TITLE_MAX);
  const yearSuffix = album.release_year ? ` (${album.release_year})` : "";
  const ratingLine =
    aggregate.rating_count > 0
      ? `${aggregate.avg_rating.toFixed(1)}★ from ${aggregate.rating_count} ${
          aggregate.rating_count === 1 ? "log" : "logs"
        }`
      : "no ratings yet";

  return new ImageResponse(
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        background: "#0b0b10",
        color: "white",
        fontFamily: "sans-serif",
      }}
    >
      {/* Top strip: brand + type label */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "32px 48px 0 48px",
        }}
      >
        <div style={{ fontSize: 36, fontWeight: 700 }}>auxd</div>
        <div
          style={{
            fontSize: 18,
            letterSpacing: 4,
            textTransform: "uppercase",
            color: "#9aa0aa",
          }}
        >
          Album
        </div>
      </div>

      {/* Middle: cover + title + artist */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 48,
          padding: "32px 48px",
          flexGrow: 1,
        }}
      >
        {album.cover_art_url ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={album.cover_art_url}
            width={400}
            height={400}
            alt=""
            style={{
              borderRadius: 12,
              objectFit: "cover",
              boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
            }}
          />
        ) : (
          <div
            style={{
              width: 400,
              height: 400,
              borderRadius: 12,
              background: "#1f2030",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 96,
              color: "#3a3c52",
            }}
          >
            ♪
          </div>
        )}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            flexGrow: 1,
            minWidth: 0,
          }}
        >
          <div style={{ fontSize: 64, fontWeight: 700, lineHeight: 1.1 }}>{title}</div>
          <div
            style={{
              fontSize: 36,
              color: "#c0c4cf",
              marginTop: 16,
              lineHeight: 1.2,
            }}
          >
            {album.artist_credit}
            {yearSuffix}
          </div>
        </div>
      </div>

      {/* Bottom: rating summary */}
      <div
        style={{
          fontSize: 28,
          color: "#9aa0aa",
          padding: "0 48px 36px 48px",
        }}
      >
        {ratingLine}
      </div>
    </div>,
    {
      width: WIDTH,
      height: HEIGHT,
      headers: { "Cache-Control": CACHE_HEADER },
    }
  );
}
