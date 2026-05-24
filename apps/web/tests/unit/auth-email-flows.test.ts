/**
 * Unit tests for the api-client 403 handler change introduced by
 * 002-auth-email-flows. The backend SessionMiddleware returns
 * ``{error: "email_unverified", message, resend_endpoint}`` for state-
 * changing requests by users who haven't verified their address yet;
 * ``isEmailUnverifiedDetail`` is the parser the toast handler keys off.
 *
 * The hook ``useResendVerification`` is intentionally not unit-tested
 * here — it is a thin useMutation wrapper around apiClient.post; the
 * meaningful surface is the 403 handler (this file) and the E2E
 * happy-path specs.
 */

import { describe, expect, it } from "vitest";

import { isEmailUnverifiedDetail } from "@/lib/api-client";

describe("isEmailUnverifiedDetail (002-auth-email-flows)", () => {
  it("returns true for the canonical email_unverified body", () => {
    expect(
      isEmailUnverifiedDetail({
        error: "email_unverified",
        message: "Verify your email to continue.",
        resend_endpoint: "/api/v1/auth/resend-verification",
      })
    ).toBe(true);
  });

  it("returns true even when message / resend_endpoint are missing", () => {
    // The parser only keys off ``error`` so it stays robust against
    // future shape evolution.
    expect(isEmailUnverifiedDetail({ error: "email_unverified" })).toBe(true);
  });

  it("returns false for the suspended 403 shape", () => {
    // Defence in depth — must not collide with the suspended-account
    // 403 redirect path.
    expect(
      isEmailUnverifiedDetail({
        error: "account_suspended",
        appeal_url: "mailto:appeals@auxd.xiejoshua.com",
      })
    ).toBe(false);
  });

  it("returns false for csrf / other 403 codes", () => {
    expect(isEmailUnverifiedDetail({ error: "csrf_token_invalid" })).toBe(false);
    expect(isEmailUnverifiedDetail({ error: "something_else" })).toBe(false);
  });

  it("returns false for null / undefined / primitives", () => {
    expect(isEmailUnverifiedDetail(null)).toBe(false);
    expect(isEmailUnverifiedDetail(undefined)).toBe(false);
    expect(isEmailUnverifiedDetail("email_unverified")).toBe(false);
    expect(isEmailUnverifiedDetail(403)).toBe(false);
    expect(isEmailUnverifiedDetail(true)).toBe(false);
  });

  it("returns false for empty objects", () => {
    expect(isEmailUnverifiedDetail({})).toBe(false);
  });

  it("returns false when the error field is not the marker value", () => {
    expect(isEmailUnverifiedDetail({ error: "EMAIL_UNVERIFIED" })).toBe(false);
    expect(isEmailUnverifiedDetail({ error: "" })).toBe(false);
    expect(isEmailUnverifiedDetail({ error: 42 })).toBe(false);
  });
});
