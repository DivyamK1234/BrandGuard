/** @type {import('next').NextConfig} */
const nextConfig = {
    // Enable React strict mode for better development experience
    reactStrictMode: true,

    // Output standalone for Docker deployment
    output: 'standalone',

    // API rewrites to proxy backend requests
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.BACKEND_URL || 'http://localhost:8000/api/:path*',
            },
        ]
    },

    // Environment variables exposed to the browser
    env: {
        NEXT_PUBLIC_APP_NAME: 'BrandGuard',
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    },
}

module.exports = nextConfig
