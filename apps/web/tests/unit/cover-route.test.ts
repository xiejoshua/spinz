import { describe, expect, it } from "vitest";

import { __test__ } from "@/app/api/cover/[size]/[mbid]/route";

const { MBID_REGEX, ALLOWED_FALLBACK_HOSTS, isFallbackAllowed } = __test__;

/**
 * REV-101 + REV-122 regression suite.
 *
 * The cover proxy at `/api/cover/[size]/[mbid]` (a) only accepts strictly
 * UUID-shaped MBIDs and (b) only 302-redirects `?fallback=` URLs whose
 * host is in the allow-list. Everything else is rejected — anonymous
 * users cannot weaponise this route into an open-redirect or for cover
 * art on arbitrary hosts.
 */

describe("MBID_REGEX (REV-122 — narrowed from {20,} to exact UUID)", () => {
  it("accepts a real MusicBrainz MBID (UUID format)", () => {
    // Real MBID for "Random Access Memories" by Daft Punk
    expect(MBID_REGEX.test("4d8b6463-5e1d-4ed9-9b80-0f55efea2bd1")).toBe(true);
  });

  it("accepts upper-case hex (case-insensitive)", () => {
    expect(MBID_REGEX.test("4D8B6463-5E1D-4ED9-9B80-0F55EFEA2BD1")).toBe(true);
  });

  it("rejects too-short hex blobs (previously accepted by {20,})", () => {
    expect(MBID_REGEX.test("aaaaaaaaaaaaaaaaaaaa")).toBe(false);
  });

  it("rejects missing-dash hex blobs (previously accepted by {20,})", () => {
    // 36 chars, all hex, no dashes — old regex would accept; new must reject.
    expect(MBID_REGEX.test("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")).toBe(false);
  });

  it("rejects oversize input even if it contains a valid MBID prefix", () => {
    expect(MBID_REGEX.test("4d8b6463-5e1d-4ed9-9b80-0f55efea2bd1-extra")).toBe(false);
  });

  it("rejects non-hex characters", () => {
    expect(MBID_REGEX.test("zzzzzzzz-5e1d-4ed9-9b80-0f55efea2bd1")).toBe(false);
  });

  it("rejects the empty string", () => {
    expect(MBID_REGEX.test("")).toBe(false);
  });
});

describe("isFallbackAllowed (REV-101 — open-redirect defence)", () => {
  it("accepts the coverartarchive.org host", () => {
    expect(
      isFallbackAllowed(
        "https://coverartarchive.org/release-group/4d8b6463-5e1d-4ed9-9b80-0f55efea2bd1/front"
      )
    ).toBe(true);
  });

  it("accepts the img.discogs.com CDN host", () => {
    expect(isFallbackAllowed("https://img.discogs.com/abc/front.jpg")).toBe(true);
  });

  it("blocks an unknown host (open-redirect attempt)", () => {
    expect(isFallbackAllowed("https://evil.example.com/phish")).toBe(false);
  });

  it("blocks unrelated subdomains of an allowed host (no suffix matching)", () => {
    // We require exact-hostname match — `attacker.coverartarchive.org.evil.com`
    // must not slip through, and neither should a totally unrelated subdomain.
    expect(isFallbackAllowed("https://evil.coverartarchive.org.example.com/x.jpg")).toBe(false);
  });

  it("blocks malformed URLs (relative paths)", () => {
    expect(isFallbackAllowed("/internal/path")).toBe(false);
  });

  it("blocks plain garbage strings that can't parse as URLs", () => {
    expect(isFallbackAllowed("not-a-url")).toBe(false);
  });

  it("blocks javascript: URLs", () => {
    expect(isFallbackAllowed("javascript:alert(1)")).toBe(false);
  });

  it("blocks data: URLs", () => {
    expect(isFallbackAllowed("data:image/png;base64,xxx")).toBe(false);
  });

  it("blocks http:// (non-https) even on an allowed host", () => {
    // Downgrade attack: never redirect to plaintext, even to a known host.
    expect(isFallbackAllowed("http://coverartarchive.org/release-group/x/front")).toBe(false);
  });

  it("blocks the empty string", () => {
    expect(isFallbackAllowed("")).toBe(false);
  });
});

describe("ALLOWED_FALLBACK_HOSTS contents", () => {
  it("contains only the two MVP cover-art hosts (defence-in-depth audit)", () => {
    expect([...ALLOWED_FALLBACK_HOSTS].sort()).toEqual(["coverartarchive.org", "img.discogs.com"]);
  });
});
