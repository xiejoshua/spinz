import { describe, expect, it } from "vitest";

import { isAccountSuspendedDetail } from "@/lib/api-client";

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
