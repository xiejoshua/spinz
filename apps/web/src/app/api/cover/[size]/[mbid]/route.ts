import { type NextRequest, NextResponse } from "next/server";

const VALID_SIZES = new Set(["250", "500", "1200"]);

const CACHE_HEADER = "public, max-age=604800, s-maxage=604800, immutable";
const NEGATIVE_CACHE_HEADER = "public, max-age=3600, s-maxage=3600";

/**
 * REV-122 — MBIDs are UUIDv4-formatted: exactly 36 chars, hex+dashes,
 * `8-4-4-4-12` layout. The previous `^[a-f0-9-]{20,}$/i` matched any 20+
 * char hex/dash blob (including `aaaaaaaaaaaaaaaaaaaa`) which composes
 * with the open-redirect (REV-101) by giving attackers a free 404 path
 * to the `?fallback=` redirect.
 */
const MBID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * REV-101 — allow-list for `?fallback=` cover URLs. The cover proxy may
 * redirect to one of these hosts when coverartarchive.org returns 404
 * (some albums only have art on Discogs). Any other host = 404, never
 * 302, to prevent the route from being used as an open-redirect for
 * phishing.
 *
 * Keep this list narrow: specific hostnames, no broad regex/suffix
 * matching. If we ever cache art on our own R2 bucket, add that
 * hostname here explicitly.
 */
const ALLOWED_FALLBACK_HOSTS = new Set<string>([
  "coverartarchive.org",
  // Discogs CDN — backend's `apps/api/src/auxd_api/providers/discogs.py`
  // emits cover_art_url values like `https://img.discogs.com/abc/front.jpg`.
  "img.discogs.com",
]);

function isFallbackAllowed(rawUrl: string): boolean {
  try {
    const u = new URL(rawUrl);
    // https only — never follow http (mixed content + downgrade attacks).
    return u.protocol === "https:" && ALLOWED_FALLBACK_HOSTS.has(u.hostname);
  } catch {
    // Malformed URL (relative path, javascript:, data:, etc.)
    return false;
  }
}

// CDN/edge caches the response via Cache-Control header. Don't force-static — the route
// reads searchParams.fallback which is genuinely dynamic per request.

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ size: string; mbid: string }> }
) {
  const { size, mbid } = await params;

  if (!VALID_SIZES.has(size)) {
    return NextResponse.json({ error: "invalid_size", allowed: [...VALID_SIZES] }, { status: 400 });
  }
  if (!MBID_REGEX.test(mbid)) {
    return NextResponse.json({ error: "invalid_mbid" }, { status: 400 });
  }

  const caaUrl = `https://coverartarchive.org/release-group/${mbid}/front-${size}`;

  try {
    const upstream = await fetch(caaUrl, { redirect: "follow", cache: "force-cache" });
    if (upstream.ok) {
      const headers = new Headers();
      const contentType = upstream.headers.get("content-type") ?? "image/jpeg";
      headers.set("Content-Type", contentType);
      headers.set("Cache-Control", CACHE_HEADER);
      return new NextResponse(upstream.body, { status: 200, headers });
    }

    if (upstream.status === 404) {
      const fallback = request.nextUrl.searchParams.get("fallback");
      if (fallback && isFallbackAllowed(fallback)) {
        return NextResponse.redirect(fallback, {
          status: 302,
          headers: { "Cache-Control": NEGATIVE_CACHE_HEADER },
        });
      }
      return new NextResponse(null, {
        status: 404,
        headers: { "Cache-Control": NEGATIVE_CACHE_HEADER },
      });
    }

    return new NextResponse(null, { status: 502 });
  } catch {
    return new NextResponse(null, { status: 502 });
  }
}

/**
 * Exported for unit testing only. Production code reaches these via
 * the route handler above.
 */
export const __test__ = {
  MBID_REGEX,
  ALLOWED_FALLBACK_HOSTS,
  isFallbackAllowed,
};
