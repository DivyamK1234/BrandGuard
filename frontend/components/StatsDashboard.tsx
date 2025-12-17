
'use client'

/**
 * StatsDashboard Component
 * 
 * Displays real-time statistics about the BrandGuard application.
 * - Request Counts (Total, Daily)
 * - Cache Performance
 * - AI Token Usage & Cost Estimates
 * - Latency Metrics
 */

import { useState, useEffect } from 'react'
import {
    Activity,
    Database,
    Zap,
    Clock,
    RefreshCw,
    TrendingUp,
    Server,
    DollarSign,
    PieChart
} from 'lucide-react'
import { clsx } from 'clsx'

interface DashboardStats {
    requests: {
        total: number
        today: number
    }
    tokens: {
        total: number
        today: number
        estimated_cost_today_usd: number
    }
    performance: {
        avg_latency_ms: number
        cache_hit_rate_percent: number
        cache_hits: number
        cache_misses: number
    }
    system: {
        redis_status: string
        last_updated: string
    }
}

export default function StatsDashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [refreshing, setRefreshing] = useState(false)

    const fetchStats = async () => {
        try {
            setRefreshing(true)
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/stats/dashboard`)
            const data = await response.json()
            
            if (!response.ok || data.error) {
                throw new Error(data.error || 'Failed to fetch stats')
            }
            
            setStats(data)
            setError(null)
        } catch (err) {
            setError('Failed to load dashboard statistics')
            console.error(err)
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }

    // Initial load and auto-refresh every 30s
    useEffect(() => {
        fetchStats()
        const interval = setInterval(fetchStats, 30000)
        return () => clearInterval(interval)
    }, [])

    if (loading && !stats) {
        return (
            <div className="flex items-center justify-center p-12">
                <RefreshCw className="w-8 h-8 text-brand-500 animate-spin" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="p-6 bg-danger/10 border border-danger/20 rounded-xl text-danger">
                {error}
                <button 
                    onClick={fetchStats}
                    className="ml-4 underline hover:text-danger-400"
                >
                    Retry
                </button>
            </div>
        )
    }

    if (!stats) return null

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header Actions */}
            <div className="flex justify-end">
                <button
                    onClick={fetchStats}
                    className="flex items-center gap-2 text-sm text-surface-400 hover:text-white transition-colors"
                >
                    <RefreshCw className={clsx("w-4 h-4", refreshing && "animate-spin")} />
                    {refreshing ? 'Refreshing...' : 'Refresh Now'}
                </button>
            </div>

            {/* Main Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="Total Verifications"
                    value={stats?.requests?.total?.toLocaleString() ?? '0'}
                    subtitle={`+${stats?.requests?.today ?? 0} today`}
                    icon={<Activity className="w-5 h-5 text-brand-400" />}
                    trend="up"
                />
                <StatCard
                    title="Cache Hit Rate"
                    value={`${stats?.performance?.cache_hit_rate_percent ?? 0}%`}
                    subtitle={`${stats?.performance?.cache_hits ?? 0} hits / ${stats?.performance?.cache_misses ?? 0} misses`}
                    icon={<Database className="w-5 h-5 text-emerald-400" />}
                    color="emerald"
                />
                <StatCard
                    title="Avg Latency"
                    value={`${stats?.performance?.avg_latency_ms ?? 0}ms`}
                    subtitle="Target: <200ms"
                    icon={<Clock className="w-5 h-5 text-amber-400" />}
                    color="amber"
                />
                <StatCard
                    title="Tokens Used (Today)"
                    value={stats?.tokens?.today?.toLocaleString() ?? '0'}
                    subtitle={`Est. Cost: $${stats?.tokens?.estimated_cost_today_usd ?? 0}`}
                    icon={<Zap className="w-5 h-5 text-purple-400" />}
                    color="purple"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Cache Efficiency Visual */}
                <div className="glass-card p-6 lg:col-span-2">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <PieChart className="w-5 h-5 text-brand-400" />
                            Cache Efficiency
                        </h3>
                    </div>
                    
                    <div className="flex items-center gap-8 justify-center p-4">
                        {/* CSS Conic Gradient Pie Chart */}
                        <div 
                            className="w-40 h-40 rounded-full flex items-center justify-center relative shadow-lg shadow-brand-500/10"
                            style={{
                                background: `conic-gradient(#10b981 ${stats?.performance?.cache_hit_rate_percent ?? 0}%, #334155 ${stats?.performance?.cache_hit_rate_percent ?? 0}%)`
                            }}
                        >
                            <div className="w-32 h-32 bg-surface-900 rounded-full flex flex-col items-center justify-center z-10">
                                <span className="text-2xl font-bold text-white">
                                    {stats?.performance?.cache_hit_rate_percent ?? 0}%
                                </span>
                                <span className="text-xs text-surface-400 uppercase tracking-wider">Efficiency</span>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                                <div>
                                    <p className="text-sm font-medium text-white">Cache Hits</p>
                                    <p className="text-xs text-surface-400">{stats?.performance?.cache_hits?.toLocaleString() ?? 0} reqs</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-surface-700" />
                                <div>
                                    <p className="text-sm font-medium text-white">Cache Misses (AI)</p>
                                    <p className="text-xs text-surface-400">{stats?.performance?.cache_misses?.toLocaleString() ?? 0} reqs</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* System Health & Cost */}
                <div className="space-y-6">
                    <div className="glass-card p-6">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Server className="w-5 h-5 text-blue-400" />
                            System Health
                        </h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg">
                                <span className="text-surface-300 text-sm">Redis Status</span>
                                <span className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                    {stats?.system?.redis_status ?? 'Unknown'}
                                </span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg">
                                <span className="text-surface-300 text-sm">API Status</span>
                                <span className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                    Online
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="glass-card p-6">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <DollarSign className="w-5 h-5 text-green-400" />
                            AI Consumption
                        </h3>
                        <div className="space-y-2">
                             <div className="flex justify-between text-sm">
                                <span className="text-surface-400">Daily Budget Usage</span>
                                <span className="text-white font-medium">${stats?.tokens?.estimated_cost_today_usd ?? 0}</span>
                            </div>
                            {/* Fake progress bar for budget visualization */}
                            <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
                                <div 
                                    className="h-full bg-green-500 rounded-full" 
                                    style={{ width: `${Math.min(((stats?.tokens?.estimated_cost_today_usd ?? 0) / 5.0) * 100, 100)}%` }} 
                                />
                            </div>
                            <p className="text-xs text-surface-500 pt-1">Assuming $5.00 daily limit</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function StatCard({ title, value, subtitle, icon, color = 'brand', trend }: any) {
    return (
        <div className="glass-card p-5 hover:border-surface-600 transition-colors group">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-surface-400 text-sm font-medium mb-1">{title}</p>
                    <h3 className="text-2xl font-bold text-white group-hover:scale-105 transition-transform origin-left">
                        {value}
                    </h3>
                </div>
                <div className={`p-2 rounded-lg bg-${color}-500/10 border border-${color}-500/20`}>
                    {icon}
                </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
                {trend === 'up' && <TrendingUp className="w-3 h-3 text-emerald-400" />}
                <p className="text-xs text-surface-500 font-medium">{subtitle}</p>
            </div>
        </div>
    )
}
