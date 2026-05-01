/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "localhost" },
      { protocol: "http", hostname: "127.0.0.1" }
    ]
  },
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [{ source: "/api/backend/:path*", destination: `${backend}/:path*` }];
  }
};

module.exports = nextConfig;
