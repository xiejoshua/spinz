import type { FollowRequestsListResponse, ProfileResponse } from "@/lib/social-types";
import { describe, expect, it } from "vitest";

// Compile-time + shallow-runtime guards on the public surface. These tests
// exist mainly so a refactor that drops a field surfaces at lint/test time
// rather than during a manual click-through of /settings/privacy.

describe("ProfileResponse contract (T151 + T152)", () => {
  it("carries the bio + private_profile + optional is_critic_seed flags", () => {
    const payload: ProfileResponse = {
      user: {
        id: "user-1",
        handle: "alice",
        display_name: "Alice",
        avatar_url: null,
        bio: "loves shoegaze",
        private_profile: true,
        is_critic_seed: true,
      },
      counts: { followers: 0, following: 0 },
      relation: "pending",
    };
    expect(payload.user.private_profile).toBe(true);
    expect(payload.user.is_critic_seed).toBe(true);
    expect(payload.relation).toBe("pending");
  });

  it("accepts a relation of 'blocked' so the profile gate can hide content", () => {
    const payload: ProfileResponse = {
      user: {
        id: "user-1",
        handle: "alice",
        display_name: "Alice",
        avatar_url: null,
        bio: null,
        private_profile: false,
      },
      counts: { followers: 0, following: 0 },
      relation: "blocked",
    };
    expect(payload.relation).toBe("blocked");
  });
});

describe("FollowRequestsListResponse contract (T148)", () => {
  it("maps a requester id → user card in the sidecar", () => {
    const payload: FollowRequestsListResponse = {
      requests: [
        {
          id: "req-1",
          requester_id: "user-bob",
          created_at: new Date().toISOString(),
        },
      ],
      users: {
        "user-bob": {
          id: "user-bob",
          handle: "bob",
          display_name: "Bob",
          avatar_url: null,
        },
      },
      next_cursor: null,
    };
    expect(payload.requests).toHaveLength(1);
    expect(payload.users[payload.requests[0].requester_id].handle).toBe("bob");
    expect(payload.next_cursor).toBeNull();
  });
});
