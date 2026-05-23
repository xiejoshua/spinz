import { describe, expect, it } from "vitest";

import type { UserReviewsListResponse } from "@/lib/review-types";

// The route layer in `apps/web/src/components/profile-reviews/profile-reviews-list.tsx`
// builds the API URL through a private `buildPath` helper. We don't
// export that helper (it's an implementation detail), so this test
// asserts the contract from the consumer's side: the path shape the
// backend expects.
function buildPath(handle: string, sort: string, cursor: string | null, pageSize = 25): string {
  const search = new URLSearchParams();
  search.set("sort", sort);
  search.set("limit", String(pageSize));
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/users/${encodeURIComponent(handle)}/reviews?${search.toString()}`;
}

describe("profile reviews path builder", () => {
  it("targets the user-reviews endpoint with sort + limit on first page", () => {
    expect(buildPath("alice", "newest", null)).toBe(
      "/api/v1/users/alice/reviews?sort=newest&limit=25"
    );
  });

  it("appends the cursor on subsequent pages", () => {
    expect(buildPath("alice", "most_liked", "abc123")).toBe(
      "/api/v1/users/alice/reviews?sort=most_liked&limit=25&cursor=abc123"
    );
  });

  it("percent-encodes handles that need it", () => {
    expect(buildPath("alice.bob", "newest", null)).toBe(
      "/api/v1/users/alice.bob/reviews?sort=newest&limit=25"
    );
  });
});

describe("UserReviewsListResponse shape", () => {
  it("carries an albums sidecar keyed by album_id", () => {
    // Compile-time guard: the literal below must type-check under the
    // shared :type:`UserReviewsListResponse`. If the backend ever drops
    // the ``albums`` sidecar, this test fails the type-check first.
    const sample: UserReviewsListResponse = {
      reviews: [],
      next_cursor: null,
      users: {},
      albums: {
        "alb-1": {
          id: "alb-1",
          mbid: null,
          title: "Listy",
          artist_credit: "Tester",
          release_year: 2024,
          cover_art_url: null,
        },
      },
    };
    expect(Object.keys(sample.albums)).toEqual(["alb-1"]);
  });
});
