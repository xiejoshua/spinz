import { ALBUM_TITLE_MAX, REVIEW_EXCERPT_MAX, backendUrl, truncate } from "@/app/api/og/helpers";
import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

/**
 * Share-card OG image generator for ``/review/[id]`` (T168).
 *
 * Renders a 1200×630 PNG. Falls back to a generic auxd card on any
 * backend / parse failure so social-crawl previews never break.
 */

export const runtime = "nodejs";

const WIDTH = 1200;
const HEIGHT = 630;
const CACHE_HEADER = "public, max-age=31536000, s-maxage=31536000, immutable";

type ReviewPayload = {
  review: {
    id: string;
    body: string;
    reactions?: {
      likes_count?: number;
    } | null;
  };
  user?: {
    handle: string;
    display_name?: string | null;
  } | null;
  album: {
    title: string;
    artist_credit: string;
    cover_art_url?: string | null;
  };
};

async function loadReview(id: string): Promise<ReviewPayload | null> {
  try {
    const response = await fetch(backendUrl(`/api/v1/reviews/${encodeURIComponent(id)}`), {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as ReviewPayload;
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
  const data = await loadReview(id);

  if (!data) {
    return new ImageResponse(<FallbackCard />, {
      width: WIDTH,
      height: HEIGHT,
      headers: { "Cache-Control": "public, max-age=300, s-maxage=300" },
    });
  }

  const { review, user, album } = data;
  const handle = user?.handle ?? "user";
  const excerpt = truncate(review.body, REVIEW_EXCERPT_MAX);
  const title = truncate(album.title, ALBUM_TITLE_MAX);
  const likesCount = review.reactions?.likes_count ?? 0;
  const likeLine = likesCount > 0 ? `${likesCount} ${likesCount === 1 ? "like" : "likes"}` : "";

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
      {/* Top strip: actor + type label */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "32px 48px 0 48px",
        }}
      >
        <div style={{ fontSize: 28, color: "#c0c4cf" }}>@{handle} · review of</div>
        <div style={{ fontSize: 28, fontWeight: 700 }}>auxd</div>
      </div>

      {/* Middle: small cover + album */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 32,
          padding: "24px 48px 0 48px",
        }}
      >
        {album.cover_art_url ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={album.cover_art_url}
            width={200}
            height={200}
            alt=""
            style={{
              borderRadius: 8,
              objectFit: "cover",
              boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            }}
          />
        ) : (
          <div
            style={{
              width: 200,
              height: 200,
              borderRadius: 8,
              background: "#1f2030",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 64,
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
            minWidth: 0,
          }}
        >
          <div style={{ fontSize: 44, fontWeight: 700, lineHeight: 1.1 }}>{title}</div>
          <div style={{ fontSize: 28, color: "#c0c4cf", marginTop: 8 }}>{album.artist_credit}</div>
        </div>
      </div>

      {/* Bottom: excerpt + likes */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 16,
          padding: "32px 48px",
          flexGrow: 1,
          justifyContent: "flex-end",
        }}
      >
        <div
          style={{
            fontSize: 30,
            color: "#e6e6f0",
            lineHeight: 1.35,
          }}
        >
          {excerpt}
        </div>
        {likeLine ? <div style={{ fontSize: 22, color: "#9aa0aa" }}>{likeLine}</div> : null}
      </div>
    </div>,
    {
      width: WIDTH,
      height: HEIGHT,
      headers: { "Cache-Control": CACHE_HEADER },
    }
  );
}
