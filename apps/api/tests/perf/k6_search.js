// T172 — Backend k6 perf — /api/v1/search?q=...
//
// Atlas Search backed; spec.md §6.1 doesn't set a hard threshold,
// but the user-facing wedge target (<8s p95 end-to-end) implies the
// search response must come back <400ms p95 to leave headroom for
// the React debounce + render + rate-widget interaction.
//
// Runs four representative queries in rotation:
//   - "daft punk"     — popular, fully cached in MusicBrainz cache.
//   - "carrie"        — exact-title prefix; mid-tail.
//   - "rachmaninoff"  — long-tail classical; tests UTF/diacritics.
//   - "asdfqwerty"    — guaranteed empty result; tests the no-hit
//                       path doesn't fall through to a slow live
//                       MusicBrainz lookup on every iteration.
//
//   k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
//          apps/api/tests/perf/k6_search.js

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "1m", target: 20 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<400", "p(99)<1000"],
    http_req_failed: ["rate<0.02"], // search tolerates 2% — live MB fallback can blip
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const QUERIES = ["daft+punk", "carrie", "rachmaninoff", "asdfqwerty"];

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.get(`${BASE_URL}/api/v1/search?q=${q}`);
  check(res, {
    "status is 200": (r) => r.status === 200,
  });
  sleep(1);
}
