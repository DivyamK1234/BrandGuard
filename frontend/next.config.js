/** @type {import('next').NextConfig} */
const nextConfig = {
    // Enable React strict mode for better development experience
    reactStrictMode: true,

    // Output standalone for Docker deployment
    output: 'standalone',

    // Environment variables exposed to the browser
    env: {
        NEXT_PUBLIC_APP_NAME: 'BrandGuard',
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    },
}

module.exports = nextConfig
