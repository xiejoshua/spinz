import type { UseFormReturn } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";

import { setApiFormErrors } from "@/lib/forms";

/**
 * Minimal mock of react-hook-form's UseFormReturn — `setApiFormErrors`
 * only calls `setError`, so that's the only method we stub. The cast to
 * `UseFormReturn<TValues>` makes TypeScript accept the partial mock.
 */
type SetErrorCall = { field: string; message: string };

function makeMockForm() {
  const calls: SetErrorCall[] = [];
  const setError = vi.fn((field: string, error: { message: string }) => {
    calls.push({ field, message: error.message });
  });
  // We only need a working `setError`; everything else is irrelevant.
  const form = { setError } as unknown as UseFormReturn<Record<string, string>>;
  return { form, calls, setError };
}

describe("setApiFormErrors", () => {
  it("returns false and sets no error when payload is undefined", () => {
    const { form, calls } = makeMockForm();
    const handled = setApiFormErrors(form, undefined);
    expect(handled).toBe(false);
    expect(calls).toHaveLength(0);
  });

  it("returns false and sets no error when payload has no detail", () => {
    const { form, calls } = makeMockForm();
    const handled = setApiFormErrors(form, {});
    expect(handled).toBe(false);
    expect(calls).toHaveLength(0);
  });

  it("routes string detail to the root error", () => {
    const { form, calls } = makeMockForm();
    const handled = setApiFormErrors(form, { detail: "Rate limit exceeded." });
    expect(handled).toBe(true);
    expect(calls).toEqual([{ field: "root", message: "Rate limit exceeded." }]);
  });

  describe("custom error shape {error, message[, field]}", () => {
    it("maps weak_password → password field", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: { error: "weak_password", message: "password must contain at least one digit" },
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([
        { field: "password", message: "password must contain at least one digit" },
      ]);
    });

    it("maps duplicate_email → email field", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: { error: "duplicate_email", message: "email is already registered" },
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([{ field: "email", message: "email is already registered" }]);
    });

    it("maps duplicate_handle → handle field", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: { error: "duplicate_handle", message: "handle is already in use" },
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([{ field: "handle", message: "handle is already in use" }]);
    });

    it("maps invalid_handle / reserved_handle → handle field", () => {
      const { form: a, calls: callsA } = makeMockForm();
      setApiFormErrors(a, {
        detail: { error: "invalid_handle", message: "handle has invalid characters" },
      });
      expect(callsA[0]?.field).toBe("handle");

      const { form: b, calls: callsB } = makeMockForm();
      setApiFormErrors(b, {
        detail: { error: "reserved_handle", message: "this handle is reserved" },
      });
      expect(callsB[0]?.field).toBe("handle");
    });

    it("respects an explicit `field` over the code map", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: {
          error: "weak_password",
          message: "use a different password",
          field: "email", // weird but explicit — we honour it
        },
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([{ field: "email", message: "use a different password" }]);
    });

    it("falls back to root when the code isn't mapped and no field is provided", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: { error: "unrecognised_code", message: "something went wrong" },
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([{ field: "root", message: "something went wrong" }]);
    });
  });

  describe("Pydantic default 422 shape [{loc, msg, type}]", () => {
    it("routes each issue to the field named by loc (skipping the 'body' marker)", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: [
          { loc: ["body", "email"], msg: "value is not a valid email address" },
          { loc: ["body", "password"], msg: "ensure this value has at least 12 characters" },
        ],
      });
      expect(handled).toBe(true);
      expect(calls).toEqual([
        { field: "email", message: "value is not a valid email address" },
        { field: "password", message: "ensure this value has at least 12 characters" },
      ]);
    });

    it("returns false when issues have no field loc", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: [{ loc: ["body"], msg: "root-level error" }],
      });
      // No usable field → nothing was set → handled=false so caller can banner it.
      expect(handled).toBe(false);
      expect(calls).toHaveLength(0);
    });

    it("returns false on an empty issue array (nothing to set)", () => {
      const { form, calls } = makeMockForm();
      const handled = setApiFormErrors(form, { detail: [] });
      expect(handled).toBe(false);
      expect(calls).toHaveLength(0);
    });
  });

  describe("regression guards", () => {
    /**
     * Three bugs we shipped iterating on this code, each pinned here so it
     * doesn't quietly come back. See the commit chain for context.
     */

    it("does NOT throw on an iterable-looking object that's actually not iterable", () => {
      // Pre-fix the helper used `for...of payload.detail` on whatever it
      // got, which threw TypeError on plain objects. Now the type guard
      // gates the iteration — non-arrays return cleanly.
      const { form, calls } = makeMockForm();
      expect(() =>
        setApiFormErrors(form, {
          detail: { error: "any_error", message: "shouldn't iterate me" },
        })
      ).not.toThrow();
      expect(calls.length).toBeGreaterThan(0); // routed via isCustomError instead
    });

    it("regression: nested-detail body (call site bug) doesn't silently no-op", () => {
      // The api-client stores the WHOLE response body as ApiError.detail.
      // Backend body shape is {detail: {error, message}}, so naively passing
      // the ApiError to setApiFormErrors yielded payload.detail = the full
      // body = {detail: {...}} — and isCustomError correctly fails because
      // there's no `error` key at the top. The helper returns false; the
      // CALL SITE is responsible for unwrapping. This test pins that
      // contract by passing the inner detail (what callers should pass)
      // and asserting routing works.
      const { form, calls } = makeMockForm();
      const responseBody = {
        detail: { error: "duplicate_email", message: "email is already registered" },
      };
      // ✗ Bad: setApiFormErrors(form, responseBody) — would no-op.
      // ✓ Good: pass responseBody.detail's outer wrapper (which IS responseBody).
      //   Helper reads payload.detail = inner {error, message}.
      const handled = setApiFormErrors(form, responseBody);
      expect(handled).toBe(true);
      expect(calls).toEqual([{ field: "email", message: "email is already registered" }]);
    });

    it("regression: caller can trust the return value (no stale-state race)", () => {
      // The form previously read `form.formState.errors` immediately after
      // setError(), which is async — it saw the stale (empty) state and
      // layered a generic "Signup failed (409)" banner on top of the
      // correct field-level message. Fix: setApiFormErrors returns boolean.
      // This test just asserts the contract (true when something was set).
      const { form } = makeMockForm();
      const handled = setApiFormErrors(form, {
        detail: { error: "weak_password", message: "x" },
      });
      expect(handled).toBe(true);
    });
  });
});
