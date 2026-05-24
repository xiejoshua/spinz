import { renderReviewBody } from "@/lib/review-body";
import { Fragment, createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

/** Render the renderer's output to a static HTML string (no JSDom needed). */
function html(body: string): string {
  return renderToStaticMarkup(createElement(Fragment, null, renderReviewBody(body)));
}

describe("renderReviewBody", () => {
  it("renders plain text inside a single paragraph", () => {
    expect(html("just text")).toBe("<p><span>just text</span></p>");
  });

  it("renders bold markdown", () => {
    expect(html("a **bold** word")).toBe("<p><span>a <strong>bold</strong> word</span></p>");
  });

  it("renders italic with asterisks", () => {
    expect(html("an *italic* word")).toBe("<p><span>an <em>italic</em> word</span></p>");
  });

  it("renders italic with underscores", () => {
    expect(html("an _italic_ word")).toBe("<p><span>an <em>italic</em> word</span></p>");
  });

  it("renders an inline https link with external-safe attrs", () => {
    const out = html("see [auxd](https://auxd.app) for more");
    expect(out).toContain('href="https://auxd.app"');
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
    expect(out).toContain(">auxd</a>");
  });

  it("renders an http (non-https) link", () => {
    expect(html("see [legacy](http://example.com)")).toContain('href="http://example.com"');
  });

  it("splits paragraphs on a blank line", () => {
    expect(html("first paragraph\n\nsecond paragraph")).toBe(
      "<p><span>first paragraph</span></p><p><span>second paragraph</span></p>",
    );
  });

  it("renders single-newline line breaks inside a paragraph", () => {
    expect(html("line one\nline two")).toBe(
      "<p><span>line one<br/></span><span>line two</span></p>",
    );
  });

  it("falls back to literal text when bold has no closing marker", () => {
    expect(html("**unclosed bold")).toBe("<p><span>**unclosed bold</span></p>");
  });

  it("treats whitespace-only inner content as bold (matches backend parse)", () => {
    // Backend's sanitizer allows it; renderer follows suit. Standard
    // markdown would consider this no-bold, but the spec's regex shape
    // is non-empty inner (`[^*]+?`), so spaces qualify.
    expect(html("not ** empty **")).toBe(
      "<p><span>not <strong> empty </strong></span></p>",
    );
  });

  it("normalises CRLF line endings to LF before splitting", () => {
    expect(html("a\r\nb\r\n\r\nc")).toBe(
      "<p><span>a<br/></span><span>b</span></p><p><span>c</span></p>",
    );
  });

  it("renders emphasis before and after a link", () => {
    const out = html("**lead** [see](https://x.test) *trail*");
    expect(out).toContain("<strong>lead</strong>");
    expect(out).toContain('href="https://x.test"');
    expect(out).toContain("<em>trail</em>");
  });

  it("collapses multiple blank lines to a single paragraph break", () => {
    expect(html("a\n\n\n\nb")).toBe("<p><span>a</span></p><p><span>b</span></p>");
  });
});
