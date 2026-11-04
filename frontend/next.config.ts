import type { NextConfig } from "next";

const rawApi = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const api = rawApi === "same-origin" ? "" : rawApi; // "same-origin" : pas d'origine externe à autoriser
const internalApi = process.env.API_INTERNAL_URL; // ex. http://api:8000 (figé au build)
const isProd = process.env.NODE_ENV === "production";

// CSP : Next.js injecte des scripts en ligne ; 'unsafe-inline' reste donc nécessaire pour script-src tant que
// les nonces ne sont pas mis en place (limite documentée dans docs/SECURITY.md). Le reste est restrictif.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self' ${api}`.trim(),
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Image Docker minimale ; activé uniquement au build conteneur (BUILD_STANDALONE=1).
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
  // Relais /api -> API (réseau Docker interne) : un seul point d'entrée pour le site et l'API.
  async rewrites() {
    return internalApi ? [{ source: "/api/:path*", destination: `${internalApi}/api/:path*` }] : [];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          ...(isProd ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }] : []),
        ],
      },
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache" }] },
    ];
  },
};

export default nextConfig;
