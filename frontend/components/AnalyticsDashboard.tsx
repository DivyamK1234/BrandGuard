'use client'

/**
 * BrandGuard Analytics Dashboard
 * 
 * Real-time analytics dashboard showing:
 * - Key metrics (total verifications, success rate, avg time, unsafe detections)
 * - Classification breakdown (pie chart)
 * - 7-day trend (line chart)
 * - Recent verifications table
 * 
 * Refreshes every 5 seconds for real-time updates.
 */

import { useEffect, useState } from 'react'
import {
    TrendingUp,
    Activity,
    Clock,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    AlertCircle,
    RefreshCw
} from 'lucide-react'

interface AnalyticsData {
    total_verifications: number
    today_count: number
    success_rate: number
    avg_processing_time_ms: number
    fraud_detections: number
    classification_breakdown: {
        SAFE: number
        RISK_HIGH: number
        RISK_MEDIUM: number
        UNKNOWN: number
    }
    classification_percentages: {
        safe: number
        risk_high: number
        risk_medium: number
        unknown: number
    }
    source_breakdown: {
        AI_GENERATED: number
        CACHE: number
        MANUAL_OVERRIDE: number
    }
    recent_verifications: Array<{
        audio_id: string
        brand_safety_score: string
        source: string
        processing_time_ms: number
        category_tags: string[]
        timestamp: string
    }>
    trend_data: Array<{
        date: string
        total: number
        safe: number
        risk_high: number
        risk_medium: number
        unknown: number
    }>
    last_updated: string
}

export default function AnalyticsDashboard() {
    const [data, setData] = useState<AnalyticsData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

    const fetchAnalytics = async () => {
        try {
            // Use relative path - Next.js will proxy to backend via rewrites
            const response = await fetch('/api/v1/analytics')
            if (!response.ok) throw new Error('Failed to fetch analytics')
            const analyticsData = await response.json()
            setData(analyticsData)
            setError(null)
            setLastRefresh(new Date())
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchAnalytics()
        const interval = setInterval(fetchAnalytics, 5000) // Refresh every 5 seconds
        return () => clearInterval(interval)
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="flex items-center gap-3 text-surface-400">
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Loading analytics...</span>
                </div>
            </div>
        )
    }

    if (error || !data) {
        return (
            <div className="glass-card p-8 text-center">
                <AlertTriangle className="w-12 h-12 text-warning mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Failed to Load Analytics</h3>
                <p className="text-surface-400 mb-4">{error || 'No data available'}</p>
                <button
                    onClick={fetchAnalytics}
                    className="btn-primary"
                >
                    Retry
                </button>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header with refresh indicator */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Analytics Dashboard</h2>
                    <p className="text-sm text-surface-400">
                        Last updated: {lastRefresh.toLocaleTimeString()}
                    </p>
                </div>
                <div className="flex items-center gap-2 text-sm text-surface-400">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Auto-refresh: 5s</span>
                </div>
            </div>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                    icon={<Activity className="w-6 h-6 text-brand-400" />}
                    label="Total Verifications"
                    value={data.total_verifications.toLocaleString()}
                    subtitle={`${data.today_count} today`}
                    trend="up"
                />
                <MetricCard
                    icon={<CheckCircle2 className="w-6 h-6 text-safe" />}
                    label="Success Rate"
                    value={`${data.success_rate}%`}
                    subtitle="Safe classifications"
                    trend={data.success_rate >= 80 ? 'up' : 'down'}
                />
                <MetricCard
                    icon={<Clock className="w-6 h-6 text-brand-400" />}
                    label="Avg Processing Time"
                    value={`${Math.round(data.avg_processing_time_ms)}ms`}
                    subtitle="Response latency"
                    trend={data.avg_processing_time_ms < 100 ? 'up' : 'neutral'}
                />
                <MetricCard
                    icon={<AlertTriangle className="w-6 h-6 text-danger" />}
                    label="Unsafe Detected"
                    value={data.classification_breakdown.RISK_HIGH.toLocaleString()}
                    subtitle={`${data.fraud_detections} fraud flags`}
                    trend="neutral"
                />
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Classification Breakdown */}
                <div className="glass-card p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Classification Breakdown</h3>
                    <div className="space-y-3">
                        <ClassificationBar
                            label="Safe"
                            percentage={data.classification_percentages.safe}
                            count={data.classification_breakdown.SAFE}
                            color="bg-safe"
                        />
                        <ClassificationBar
                            label="Risk Medium"
                            percentage={data.classification_percentages.risk_medium}
                            count={data.classification_breakdown.RISK_MEDIUM}
                            color="bg-warning"
                        />
                        <ClassificationBar
                            label="Risk High"
                            percentage={data.classification_percentages.risk_high}
                            count={data.classification_breakdown.RISK_HIGH}
                            color="bg-danger"
                        />
                        <ClassificationBar
                            label="Unknown"
                            percentage={data.classification_percentages.unknown}
                            count={data.classification_breakdown.UNKNOWN}
                            color="bg-surface-600"
                        />
                    </div>
                </div>

                {/* 7-Day Trend */}
                <div className="glass-card p-6">
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <TrendingUp className="w-5 h-5 text-brand-400" />
                        7-Day Verification Trend
                    </h3>
                    <div className="h-48">
                        <TrendChart data={data.trend_data} />
                    </div>
                </div>
            </div>

            {/* Recent Verifications Table */}
            <div className="glass-card p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Recent Verifications</h3>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-surface-800">
                                <th className="text-left py-3 px-4 text-sm font-medium text-surface-400">Audio ID</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-surface-400">Classification</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-surface-400">Source</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-surface-400">Time</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-surface-400">Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.recent_verifications.map((verification, idx) => (
                                <tr key={idx} className="border-b border-surface-800/50 hover:bg-surface-900/50 transition-colors">
                                    <td className="py-3 px-4 text-sm text-white font-mono">{verification.audio_id}</td>
                                    <td className="py-3 px-4">
                                        <ClassificationBadge score={verification.brand_safety_score} />
                                    </td>
                                    <td className="py-3 px-4">
                                        <SourceBadge source={verification.source} />
                                    </td>
                                    <td className="py-3 px-4 text-sm text-surface-300">
                                        {Math.round(verification.processing_time_ms)}ms
                                    </td>
                                    <td className="py-3 px-4 text-sm text-surface-400">
                                        {new Date(verification.timestamp).toLocaleTimeString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {data.recent_verifications.length === 0 && (
                        <div className="text-center py-8 text-surface-500">
                            No verifications yet. Upload an audio file to get started!
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

// Metric Card Component
function MetricCard({
    icon,
    label,
    value,
    subtitle,
    trend
}: {
    icon: React.ReactNode
    label: string
    value: string
    subtitle: string
    trend: 'up' | 'down' | 'neutral'
}) {
    return (
        <div className="glass-card p-6 space-y-3">
            <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-surface-800/50 flex items-center justify-center">
                    {icon}
                </div>
                {trend === 'up' && <TrendingUp className="w-5 h-5 text-safe" />}
            </div>
            <div>
                <p className="text-sm text-surface-400 mb-1">{label}</p>
                <p className="text-3xl font-bold text-white">{value}</p>
                <p className="text-xs text-surface-500 mt-1">{subtitle}</p>
            </div>
        </div>
    )
}

// Classification Bar Component
function ClassificationBar({
    label,
    percentage,
    count,
    color
}: {
    label: string
    percentage: number
    count: number
    color: string
}) {
    return (
        <div>
            <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-surface-300">{label}</span>
                <span className="text-sm text-surface-400">{count} ({percentage}%)</span>
            </div>
            <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} transition-all duration-500`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    )
}

// Trend Chart Component (Simple Bar Chart)
function TrendChart({ data }: { data: AnalyticsData['trend_data'] }) {
    const maxValue = Math.max(...data.map(d => d.total), 1)

    return (
        <div className="flex items-end justify-between h-full gap-2">
            {data.map((day, idx) => {
                const heightPercentage = (day.total / maxValue) * 100
                return (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-2">
                        <div className="w-full flex flex-col justify-end h-40">
                            <div
                                className="w-full bg-gradient-to-t from-brand-500 to-brand-400 rounded-t-lg transition-all duration-500 hover:from-brand-400 hover:to-brand-300"
                                style={{ height: `${heightPercentage}%` }}
                                title={`${day.total} verifications`}
                            />
                        </div>
                        <div className="text-xs text-surface-500 text-center">
                            {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

// Classification Badge
function ClassificationBadge({ score }: { score: string }) {
    const config = {
        SAFE: { icon: CheckCircle2, color: 'text-safe', bg: 'bg-safe/10' },
        RISK_MEDIUM: { icon: AlertCircle, color: 'text-warning', bg: 'bg-warning/10' },
        RISK_HIGH: { icon: XCircle, color: 'text-danger', bg: 'bg-danger/10' },
        UNKNOWN: { icon: AlertCircle, color: 'text-surface-400', bg: 'bg-surface-800' }
    }

    const { icon: Icon, color, bg } = config[score as keyof typeof config] || config.UNKNOWN

    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${color} ${bg}`}>
            <Icon className="w-3.5 h-3.5" />
            {score}
        </span>
    )
}

// Source Badge
function SourceBadge({ source }: { source: string }) {
    const config = {
        AI_GENERATED: { label: 'AI', color: 'text-brand-400 bg-brand-400/10' },
        CACHE: { label: 'Cache', color: 'text-safe bg-safe/10' },
        MANUAL_OVERRIDE: { label: 'Override', color: 'text-warning bg-warning/10' }
    }

    const { label, color } = config[source as keyof typeof config] || { label: source, color: 'text-surface-400 bg-surface-800' }

    return (
        <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
            {label}
        </span>
    )
}
