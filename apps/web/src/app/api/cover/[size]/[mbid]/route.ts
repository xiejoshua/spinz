import { type NextRequest, NextResponse } from "next/server";

const VALID_SIZES = new Set(["250", "500", "1200"]);

const CACHE_HEADER = "public, max-age=604800, s-maxage=604800, immutable";
const NEGATIVE_CACHE_HEADER = "public, max-age=3600, s-maxage=3600";

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
  if (!/^[a-f0-9-]{20,}$/i.test(mbid)) {
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
      if (fallback?.startsWith("https://")) {
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
