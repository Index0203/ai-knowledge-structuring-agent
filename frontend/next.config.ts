import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The production image runs the standalone server instead of the full Next.js CLI.
  output: "standalone",
};

export default nextConfig;
