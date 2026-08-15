/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API base URL is injected at build/runtime via NEXT_PUBLIC_API_URL
  // (see .env.example) — never hardcode backend URLs in components.
};

module.exports = nextConfig;
