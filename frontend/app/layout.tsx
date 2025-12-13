import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
    subsets: ['latin'],
    variable: '--font-inter',
})

export const metadata: Metadata = {
    title: 'BrandGuard | Audio Safety Verification',
    description: 'AI-powered audio content classification for brand safety in digital advertising',
    keywords: ['brand safety', 'audio verification', 'ad tech', 'AI', 'content moderation'],
    authors: [{ name: 'DoubleVerify' }],
    openGraph: {
        title: 'BrandGuard | Audio Safety Verification',
        description: 'AI-powered audio content classification for brand safety',
        type: 'website',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" className="dark">
            <head>
                <link rel="icon" href="/favicon.ico" sizes="any" />
            </head>
            <body className={`${inter.variable} font-sans`}>
                {/* Background gradient overlay */}
                <div className="fixed inset-0 -z-10">
                    <div className="absolute inset-0 bg-gradient-to-br from-surface-900 via-surface-950 to-black" />
                    <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-brand-600/5 blur-3xl rounded-full" />
                    <div className="absolute bottom-0 left-0 w-1/3 h-1/3 bg-brand-500/5 blur-3xl rounded-full" />
                </div>

                {children}
            </body>
        </html>
    )
}
