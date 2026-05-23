/** @type {import('next').NextConfig} */

// Backend host for the rewrites proxy. Required in prod (https://api.xiejoshua.com)
// and local dev (http://localhost:8000). Falls back to localhost so a developer
// who hasn't set the env var doesn't get a confusing rewrite to undefined.
const API_BACKEND_URL = process.env.API_BACKEND_URL ?? "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@auxd/shared-types"],
  async rewrites() {
    // Same-origin proxy: browser calls /api/v1/* on xiejoshua.com, which
    // Next.js (running on Vercel) server-side-fetches from API_BACKEND_URL.
    // Result: session cookies are first-party on xiejoshua.com so the SSR
    // layout can read them; no CORS / cross-subdomain cookie domain
    // gymnastics. Also covers /healthz proxying for uptime checks.
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_BACKEND_URL}/api/v1/:path*`,
      },
      {
        source: "/healthz",
        destination: `${API_BACKEND_URL}/healthz`,
      },
    ];
  },
};

export default nextConfig;
