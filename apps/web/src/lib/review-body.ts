import { type ReactNode, createElement } from "react";

/**
 * Review-body markdown renderer.
 *
 * Mirrors the allowlist enforced by the backend's
 * ``auxd_api.modules.reviews.service.sanitize_markdown``:
 *
 *   - ``**bold**`` → ``<strong>``
 *   - ``*italic*`` / ``_italic_`` → ``<em>``
 *   - ``[text](http(s)://url)`` → ``<a href>``
 *   - single ``\n`` → ``<br>``
 *   - double ``\n\n`` → paragraph break (``<p>``)
 *
 * The backend stores markdown SOURCE and guarantees no HTML, no
 * non-http(s) link schemes, and no control characters — so this
 * renderer can trust its input and stays free of escaping/XSS work.
 *
 * Nested emphasis (e.g. ``**bold *italic* inside**``) is intentionally
 * NOT supported — the regex `[^*]+?` rejects an inner ``*`` inside
 * ``**…**``, matching the server's parse model (which uses the same
 * shape). Anything that looks like nesting falls through to literal text.
 *
 * Backslash escapes (``\*literal\*``) are not supported either — the
 * sanitizer doesn't carry escapes, so adding them client-side would
 * give a different read than what the user wrote in the editor.
 *
 * The file is `.ts` (not `.tsx`) and uses `createElement` directly so
 * vitest's Node-environment runner doesn't need a JSX transform for
 * this module.
 */

const LINK_RE = /\[([^\]]+?)\]\((https?:\/\/[^)]+)\)/g;
const INLINE_RE = /(\*\*([^*]+?)\*\*)|(\*([^*]+?)\*)|(_([^_]+?)_)/;

type KeyGen = () => number;

/** Top-level entry — splits the body into paragraphs + line breaks + inline. */
export function renderReviewBody(body: string): ReactNode[] {
  // Normalise CRLF → LF defensively. Backend already does this, but it
  // costs nothing on the client and protects against pasted bodies that
  // bypassed re-sanitization (legacy rows, manual DB edits, etc.).
  const normalised = body.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const paragraphs = normalised.split(/\n{2,}/);
  return paragraphs.map((paragraph, i) => {
    const lines = paragraph.split("\n");
    const lineNodes: ReactNode[] = lines.map((line, j) => {
      const isLast = j === lines.length - 1;
      const children: ReactNode[] = renderInline(line);
      if (!isLast) children.push(createElement("br", { key: "br" }));
      return createElement("span", { key: `l-${i}-${j}-${line.length}` }, ...children);
    });
    return createElement("p", { key: `p-${i}-${paragraph.length}` }, ...lineNodes);
  });
}

/** Inline pass — extracts links first, then emphasis on the gaps. */
function renderInline(text: string): ReactNode[] {
  if (text.length === 0) return [];

  const nodes: ReactNode[] = [];
  let counter = 0;
  const nextKey: KeyGen = () => counter++;

  let lastEnd = 0;
  // Reset .lastIndex because LINK_RE is /g — re-using the literal across
  // invocations would otherwise leak state into the next call.
  LINK_RE.lastIndex = 0;
  let match: RegExpExecArray | null = LINK_RE.exec(text);
  while (match !== null) {
    if (match.index > lastEnd) {
      pushEmphasis(text.slice(lastEnd, match.index), nodes, nextKey);
    }
    nodes.push(
      createElement(
        "a",
        {
          key: `a-${nextKey()}`,
          href: match[2],
          target: "_blank",
          rel: "noopener noreferrer",
          style: { color: "var(--link)", textDecoration: "underline" },
        },
        match[1]
      )
    );
    lastEnd = match.index + match[0].length;
    match = LINK_RE.exec(text);
  }
  if (lastEnd < text.length) {
    pushEmphasis(text.slice(lastEnd), nodes, nextKey);
  }
  return nodes;
}

/** Emphasis pass — finds leftmost bold/italic match and recurses on the gap. */
function pushEmphasis(text: string, sink: ReactNode[], nextKey: KeyGen): void {
  let remaining = text;
  while (remaining.length > 0) {
    const m = INLINE_RE.exec(remaining);
    if (!m || m.index === undefined) {
      sink.push(remaining);
      return;
    }
    if (m.index > 0) sink.push(remaining.slice(0, m.index));

    if (m[1] !== undefined) {
      sink.push(createElement("strong", { key: `b-${nextKey()}` }, m[2]));
    } else if (m[3] !== undefined) {
      sink.push(createElement("em", { key: `i-${nextKey()}` }, m[4]));
    } else if (m[5] !== undefined) {
      sink.push(createElement("em", { key: `u-${nextKey()}` }, m[6]));
    }

    remaining = remaining.slice(m.index + m[0].length);
  }
}
