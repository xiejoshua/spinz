// T172 — Backend k6 perf — /api/v1/feed home read.
//
// Spec.md §6.1 sets p95<500ms for the home feed (per-pageview from
// PostHog). This k6 spec measures *backend-only* response time (no
// React hydration, no asset payload, no CDN). The backend budget is
// derived: with a ~200ms client-side budget for React + assets, the
// backend must answer in <300ms p95 to keep the end-to-end p95<500ms.
//
//   k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
//          --env SESSION_COOKIE='auxd_session=...' \
//          apps/api/tests/perf/k6_feed_home.js
//
// Run against a staging account that has ≥50 followees with ≥10
// diary entries each, otherwise the feed is too small to stress the
// scoring pass. The critic-seed roster (T117) gives us that for
// free if the operator has followed all of them on the test account.

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 30 },
    { duration: "1m", target: 30 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<300", "p(99)<700"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SESSION_COOKIE = __ENV.SESSION_COOKIE || "";

export default function () {
  const params = {
    headers: SESSION_COOKIE ? { Cookie: SESSION_COOKIE } : {},
  };
  // Match real feed cadence (initial load + occasional refresh).
  const res = http.get(`${BASE_URL}/api/v1/feed?mode=for_you&limit=25`, params);
  check(res, {
    "status is 200": (r) => r.status === 200,
    "has entries field": (r) => r.body && r.body.includes("entries"),
  });
  sleep(2);
}
