/**
 * Shared helpers for the share-card OG image generators (T168).
 *
 * The actual `ImageResponse` JSX lives in the per-target route files
 * (album / review). Here we keep the pure helpers — string trimming,
 * fallback resolution, backend-URL resolution — so they can be
 * unit-tested without spinning up the Next.js runtime.
 */

/**
 * Trim ``text`` to ``maxLength`` characters with a Unicode ellipsis.
 *
 * Empty strings round-trip unchanged. Strings already within budget
 * pass through verbatim. Trailing whitespace before the ellipsis is
 * stripped so we don't render " …".
 */
export function truncate(text: string, maxLength: number): string {
  if (!text) return text;
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}…`;
}

/**
 * Resolve the backend URL the OG route should hit for data.
 *
 * Production sets ``API_BACKEND_URL`` so the OG route reaches the live
 * FastAPI. Local development falls back to ``http://localhost:8000``
 * which mirrors :mod:`apps/web/src/lib/api-server.ts`.
 */
export function backendUrl(path: string): string {
  const base = process.env.API_BACKEND_URL ?? "http://localhost:8000";
  return new URL(path, base).toString();
}

/**
 * Hard cap on the review excerpt rendered into the OG image. Beyond
 * 200 characters the text reflows past the card and looks broken; the
 * truncation contract is therefore part of the visual spec, not just
 * a defensive heuristic.
 */
export const REVIEW_EXCERPT_MAX = 200;

/**
 * Hard cap on the album title rendered into the OG image. The font
 * scales down for long titles in CSS, but past 80 characters we'd
 * still overflow the image's safe area.
 */
export const ALBUM_TITLE_MAX = 80;
