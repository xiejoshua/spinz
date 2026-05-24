import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, isAccountSuspendedDetail } from "@/lib/api-client";

describe("isAccountSuspendedDetail (T159)", () => {
  it("returns true when detail carries the canonical account_suspended marker", () => {
    expect(
      isAccountSuspendedDetail({
        error: "account_suspended",
        appeal_url: "mailto:appeals@auxd.xiejoshua.com",
      })
    ).toBe(true);
  });

  it("returns false for non-suspended 403 bodies", () => {
    expect(isAccountSuspendedDetail({ error: "csrf_token_invalid" })).toBe(false);
  });

  it("returns false for null / undefined / primitives", () => {
    expect(isAccountSuspendedDetail(null)).toBe(false);
    expect(isAccountSuspendedDetail(undefined)).toBe(false);
    expect(isAccountSuspendedDetail("account_suspended")).toBe(false);
    expect(isAccountSuspendedDetail(403)).toBe(false);
  });

  it("ignores objects whose `error` field is not the marker value", () => {
    expect(isAccountSuspendedDetail({ error: "something_else" })).toBe(false);
    expect(isAccountSuspendedDetail({})).toBe(false);
  });
});

describe("apiFetch CSRF wiring (T173 security review)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 }))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not send X-CSRF-Token on GET (safe method)", async () => {
    // No `document` in node — reader returns "" early; header should not appear.
    await apiFetch("/api/v1/me", { method: "GET" });
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    expect(Object.keys(init.headers as Record<string, string>)).not.toContain("X-CSRF-Token");
  });

  it("attempts to lift the CSRF cookie on POST when document exists", async () => {
    // Simulate a browser-side `document.cookie` containing the auxd_csrf cookie.
    vi.stubGlobal("document", { cookie: "auxd_csrf=token-xyz; auxd_session=opaque" });
    await apiFetch("/api/v1/diary", { method: "POST", body: { id: "x" } });
    const init = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("token-xyz");
  });

  it("omits the header when no cookie present (SSR or signed-out)", async () => {
    vi.stubGlobal("document", { cookie: "" });
    await apiFetch("/api/v1/diary", { method: "POST", body: { id: "x" } });
    const init = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });
});
