'use client'

/**
 * BrandGuard Dashboard - Main Page
 * 
 * Modern, professional dashboard with two main views:
 * - Tab 1: Demo Client (Spotify-like audio analyzer)
 * - Tab 2: Admin Console (Override management)
 * 
 * Reference: ADVERIFY-UI - Management UI Epic
 */

import { useState } from 'react'
import {
    Shield,
    Settings,
    Headphones,
    BarChart3,
    Zap
} from 'lucide-react'
import AudioAnalyzer from '@/components/AudioAnalyzer'
import AdminConsole from '@/components/AdminConsole'
import AnalyticsDashboard from '@/components/AnalyticsDashboard'

type TabType = 'demo' | 'admin' | 'analytics'

export default function Home() {
    const [activeTab, setActiveTab] = useState<TabType>('demo')

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="border-b border-surface-800/50 backdrop-blur-xl bg-surface-950/80 sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        {/* Logo */}
                        <div className="flex items-center gap-3">
                            <div className="relative">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-glow">
                                    <Shield className="w-6 h-6 text-white" />
                                </div>
                                <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-safe rounded-full border-2 border-surface-950 animate-pulse" />
                            </div>
                            <div>
                                <h1 className="text-xl font-bold text-white">BrandGuard</h1>
                                <p className="text-xs text-surface-400">Audio Safety Verification</p>
                            </div>
                        </div>

                        {/* Status indicators */}
                        <div className="hidden md:flex items-center gap-6">
                            <div className="flex items-center gap-2 text-sm text-surface-400">
                                <div className="w-2 h-2 rounded-full bg-safe animate-pulse" />
                                <span>API Connected</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-surface-400">
                                <Zap className="w-4 h-4 text-brand-400" />
                                <span>Gemini</span>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Tab Navigation */}
            <nav className="border-b border-surface-800/50 bg-surface-950/50 backdrop-blur-lg">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex gap-2">
                        <button
                            onClick={() => setActiveTab('demo')}
                            className={`tab-button flex items-center gap-2 ${activeTab === 'demo' ? 'active' : ''}`}
                        >
                            <Headphones className="w-4 h-4" />
                            Demo Client
                        </button>
                        <button
                            onClick={() => setActiveTab('admin')}
                            className={`tab-button flex items-center gap-2 ${activeTab === 'admin' ? 'active' : ''}`}
                        >
                            <Settings className="w-4 h-4" />
                            Admin Console
                        </button>
                        <button
                            onClick={() => setActiveTab('analytics')}
                            className={`tab-button flex items-center gap-2 ${activeTab === 'analytics' ? 'active' : ''}`}
                        >
                            <BarChart3 className="w-4 h-4" />
                            Analytics
                        </button>
                    </div>
                </div>
            </nav>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-6 py-8">
                {activeTab === 'demo' ? (
                    <DemoClientView />
                ) : activeTab === 'admin' ? (
                    <AdminConsoleView />
                ) : (
                    <AnalyticsView />
                )}
            </main>

            {/* Footer */}
            <footer className="border-t border-surface-800/50 py-6 mt-auto">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-surface-500">
                        <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4" />
                            <span>BrandGuard v1.0.0</span>
                        </div>
                        <div className="flex items-center gap-6">
                            <span>Brand Safety Architecture</span>
                            <span className="flex items-center gap-1">
                                <BarChart3 className="w-4 h-4" />
                                P95 Target: &lt;20ms
                            </span>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    )
}

/**
 * Demo Client View - The "Spotify" Experience
 * 
 * Features:
 * - MP3 upload with drag-and-drop
 * - Waveform visualization with wavesurfer.js
 * - Red regions for unsafe content
 * - Real-time API integration
 * 
 */
function DemoClientView() {
    return (
        <div className="space-y-8">
            {/* Hero section */}
            <div className="text-center space-y-4 py-8">
                <h2 className="text-4xl font-bold text-gradient">
                    Audio Safety Analysis
                </h2>
                <p className="text-lg text-surface-400 max-w-2xl mx-auto">
                    Upload your audio file and let our AI-powered system analyze it for brand safety.
                    Powered by Gemini with real-time classification.
                </p>
            </div>

            {/* Audio Analyzer Component */}
            <AudioAnalyzer />

            {/* Features grid */}
            <div className="grid md:grid-cols-2 gap-6 pt-8">
                <FeatureCard
                    icon={<Shield className="w-6 h-6 text-brand-400" />}
                    title="Brand Safety Classification"
                    description="Real-time classification into SAFE, RISK_MEDIUM, RISK_HIGH categories"
                />
                <FeatureCard
                    icon={<BarChart3 className="w-6 h-6 text-safe" />}
                    title="Visual Unsafe Regions"
                    description="See exactly where problematic content appears in the audio waveform"
                />
            </div>
        </div>
    )
}

/**
 * Admin Console View - Override Management
 * 
 * Features:
 * - Override table with search/filter
 * - CRUD operations for manual overrides
 * - Real-time sync with backend
 * 
 * Reference: ADVERIFY-UI-1 - Domain Override Management
 */
function AdminConsoleView() {
    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Manual Overrides</h2>
                    <p className="text-surface-400">
                        Manage audio classification overrides. Changes take effect within 60 seconds.
                    </p>
                </div>
            </div>

            {/* Admin Console Component */}
            <AdminConsole />
        </div>
    )
}

/**
 * Analytics View - Real-Time Metrics Dashboard
 * 
 * Features:
 * - Key metrics (total verifications, success rate, avg time)
 * - Classification breakdown
 * - 7-day trend chart
 * - Recent verifications table
 * 
 * Reference: Custom Analytics Dashboard Feature
 */
function AnalyticsView() {
    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Real-Time Analytics</h2>
                    <p className="text-surface-400">
                        Monitor verification metrics and trends in real-time
                    </p>
                </div>
            </div>

            {/* Analytics Dashboard Component */}
            <AnalyticsDashboard />
        </div>
    )
}


/**
 * Feature Card Component
 */
function FeatureCard({
    icon,
    title,
    description
}: {
    icon: React.ReactNode
    title: string
    description: string
}) {
    return (
        <div className="glass-card p-6 space-y-4">
            <div className="w-12 h-12 rounded-xl bg-surface-800/50 flex items-center justify-center">
                {icon}
            </div>
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <p className="text-sm text-surface-400">{description}</p>
        </div>
    )
}
