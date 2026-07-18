/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy /api/* to the backend so SSE and CORS "just work" in dev.
    // API_PROXY_TARGET (server-only) lets dev point at a remote backend
    // without switching the client to direct cross-origin calls.
    const api =
      process.env.API_PROXY_TARGET ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};
export default nextConfig;
