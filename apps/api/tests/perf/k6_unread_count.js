// T172 — Backend k6 perf — /api/v1/notifications/unread-count.
//
// This is the highest-traffic poll endpoint (T141 client polls at
// 120 req/min per active session). Spec.md §6.1 sets a per-endpoint
// p95<400ms guard for read-heavy paths (NotificationCounter is
// MongoDB single-document fetch, no fan-out — should be sub-50ms
// even at 200 VUs).
//
// Operator note: requires a valid session cookie. Set via
//
//   k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
//          --env SESSION_COOKIE='auxd_session=...' \
//          apps/api/tests/perf/k6_unread_count.js
//
// The session cookie can be lifted from a logged-in browser
// devtools session (sandbox staging only — never share production
// cookies).

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 100 },
    { duration: "1m", target: 100 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<400", "p(99)<800"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SESSION_COOKIE = __ENV.SESSION_COOKIE || "";

export default function () {
  const params = {
    headers: SESSION_COOKIE ? { Cookie: SESSION_COOKIE } : {},
  };
  const res = http.get(`${BASE_URL}/api/v1/notifications/unread-count`, params);
  check(res, {
    "status is 200": (r) => r.status === 200,
    "has count field": (r) => r.body && r.body.includes("count"),
  });
  // Match real client polling cadence (every 0.5s = 120/min).
  sleep(0.5);
}
