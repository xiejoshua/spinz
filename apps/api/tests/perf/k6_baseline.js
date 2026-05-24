// T172 — Backend k6 baseline load test (spec.md §6.1 NFR thresholds).
//
// Runs the simplest possible smoke against /healthz to validate
// platform plumbing (Fly machines reachable, autoscaler warm, no
// gateway 502s under load). Thresholds set tight because /healthz
// must NOT touch the database, MusicBrainz, R2, or anything that
// could legitimately spike. If this exceeds p(95)<500 then routing
// or app-level startup is dragging.
//
// Not run in CI — operator-driven. Document in `docs/perf-audit.md`:
//
//   k6 run --env BASE_URL=https://api.auxd-staging.fly.dev \
//          apps/api/tests/perf/k6_baseline.js
//
// k6 is the OSS load test tool from Grafana Labs. Install via:
//   brew install k6      # macOS
//   apt-get install k6    # Linux
// or via the Docker image grafana/k6:latest.

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 50 }, // ramp to 50 VUs
    { duration: "1m", target: 50 },  // sustain
    { duration: "15s", target: 0 },  // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"], // spec.md §6.1
    http_req_failed: ["rate<0.01"],                  // <1% errors
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE_URL}/healthz`);
  check(res, {
    "status is 200": (r) => r.status === 200,
    "body has ok": (r) => r.body && r.body.includes("ok"),
  });
  sleep(1);
}
