import type { NextConfig } from "next";

// Static export: `npm run build` writes plain HTML/JS/CSS to ./out, which the
// FastAPI backend serves at "/". In development the UI calls the API at
// NEXT_PUBLIC_API_BASE (default http://localhost:8000).
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
