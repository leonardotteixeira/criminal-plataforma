import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" só no build do Docker (no Windows o rastreamento de arquivos exige symlinks).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
