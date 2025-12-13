'use client'

/**
 * AdminConsole Component
 * 
 * The "DoubleVerify" experience for managing manual overrides.
 * 
 * Features:
 * - Override table with pagination and search
 * - Add/Edit/Delete override operations
 * - Real-time sync with backend API
 * 
 * Reference: ADVERIFY-UI-1 - Domain Override Management
 * Implements: S-2.1.1 (UI Table & Search), S-2.1.2 (Override Form)
 */

import { useState, useEffect, useCallback } from 'react'
import {
    Plus,
    Search,
    Pencil,
    Trash2,
    X,
    Loader2,
    AlertTriangle,
    CheckCircle,
    AlertCircle,
    HelpCircle,
    RefreshCw,
    Shield
} from 'lucide-react'
import { clsx } from 'clsx'

// Types matching backend models.py
type BrandSafetyScore = 'SAFE' | 'RISK_HIGH' | 'RISK_MEDIUM' | 'UNKNOWN'

interface OverrideRecord {
    audio_id: string
    brand_safety_score: BrandSafetyScore
    fraud_flag: boolean
    category_tags: string[]
    reason: string | null
    created_by: string | null
    created_at: string
    updated_at: string
}

interface OverrideFormData {
    audio_id: string
    brand_safety_score: BrandSafetyScore
    fraud_flag: boolean
    category_tags: string
    reason: string
    created_by: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

export default function AdminConsole() {
    // State
    const [overrides, setOverrides] = useState<OverrideRecord[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [editingOverride, setEditingOverride] = useState<OverrideRecord | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

    // Form state
    const [formData, setFormData] = useState<OverrideFormData>({
        audio_id: '',
        brand_safety_score: 'SAFE',
        fraud_flag: false,
        category_tags: '',
        reason: '',
        created_by: 'teamSpambots'
    })

    // Fetch overrides
    const fetchOverrides = useCallback(async () => {
        setIsLoading(true)
        setError(null)

        try {
            const url = searchQuery
                ? `${API_BASE}/api/v1/admin/override?search=${encodeURIComponent(searchQuery)}`
                : `${API_BASE}/api/v1/admin/override`

            const response = await fetch(url)
            if (!response.ok) throw new Error(`Failed to fetch: ${response.status}`)

            const data: OverrideRecord[] = await response.json()
            setOverrides(data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load overrides')
        } finally {
            setIsLoading(false)
        }
    }, [searchQuery])

    useEffect(() => {
        fetchOverrides()
    }, [fetchOverrides])

    // Open modal for new override
    const openNewModal = () => {
        setEditingOverride(null)
        setFormData({
            audio_id: '',
            brand_safety_score: 'SAFE',
            fraud_flag: false,
            category_tags: '',
            reason: '',
            created_by: 'teamSpambots'
        })
        setIsModalOpen(true)
    }

    // Open modal for editing
    const openEditModal = (override: OverrideRecord) => {
        setEditingOverride(override)
        setFormData({
            audio_id: override.audio_id,
            brand_safety_score: override.brand_safety_score,
            fraud_flag: override.fraud_flag,
            category_tags: override.category_tags.join(', '),
            reason: override.reason || '',
            created_by: override.created_by || 'teamSpambots'
        })
        setIsModalOpen(true)
    }

    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsSubmitting(true)
        setError(null)

        try {
            const payload = {
                audio_id: formData.audio_id,
                brand_safety_score: formData.brand_safety_score,
                fraud_flag: formData.fraud_flag,
                category_tags: formData.category_tags.split(',').map(t => t.trim()).filter(Boolean),
                reason: formData.reason || null,
                created_by: formData.created_by || null
            }

            const isEdit = !!editingOverride
            const url = isEdit
                ? `${API_BASE}/api/v1/admin/override/${editingOverride.audio_id}`
                : `${API_BASE}/api/v1/admin/override`

            const response = await fetch(url, {
                method: isEdit ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })

            if (!response.ok) throw new Error(`Failed to save: ${response.status}`)

            setIsModalOpen(false)
            fetchOverrides()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save override')
        } finally {
            setIsSubmitting(false)
        }
    }

    // Handle delete
    const handleDelete = async (audioId: string) => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/admin/override/${audioId}`, {
                method: 'DELETE'
            })

            if (!response.ok) throw new Error(`Failed to delete: ${response.status}`)

            setDeleteConfirm(null)
            fetchOverrides()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete override')
        }
    }

    // Format date
    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    // Status badge component
    const StatusBadge = ({ score }: { score: BrandSafetyScore }) => {
        const config = {
            SAFE: { class: 'badge-safe', icon: <CheckCircle className="w-3 h-3" /> },
            RISK_MEDIUM: { class: 'badge-warning', icon: <AlertTriangle className="w-3 h-3" /> },
            RISK_HIGH: { class: 'badge-danger', icon: <AlertCircle className="w-3 h-3" /> },
            UNKNOWN: { class: 'badge-unknown', icon: <HelpCircle className="w-3 h-3" /> }
        }
        const { class: badgeClass, icon } = config[score]
        return (
            <span className={clsx(badgeClass, 'flex items-center gap-1')}>
                {icon}
                {score.replace('_', ' ')}
            </span>
        )
    }

    return (
        <div className="space-y-6">
            {/* Toolbar */}
            <div className="flex flex-col sm:flex-row gap-4 justify-between">
                {/* Search */}
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
                    <input
                        type="text"
                        placeholder="Search by Audio ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="input-field pl-10"
                    />
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                    <button
                        onClick={fetchOverrides}
                        className="btn-secondary flex items-center gap-2"
                        disabled={isLoading}
                    >
                        <RefreshCw className={clsx('w-4 h-4', isLoading && 'animate-spin')} />
                        Refresh
                    </button>
                    <button
                        onClick={openNewModal}
                        className="btn-glow flex items-center gap-2"
                    >
                        <Plus className="w-5 h-5" />
                        Add Override
                    </button>
                </div>
            </div>

            {/* Error banner */}
            {error && (
                <div className="glass-card p-4 border border-danger/30 bg-danger/10">
                    <div className="flex items-center gap-3 text-danger">
                        <AlertCircle className="w-5 h-5" />
                        <span>{error}</span>
                    </div>
                </div>
            )}

            {/* Table */}
            <div className="glass-card overflow-hidden">
                {isLoading ? (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
                    </div>
                ) : overrides.length === 0 ? (
                    <div className="text-center py-16">
                        <Shield className="w-12 h-12 text-surface-600 mx-auto mb-4" />
                        <p className="text-surface-400">
                            {searchQuery ? 'No overrides match your search' : 'No overrides configured'}
                        </p>
                        <button
                            onClick={openNewModal}
                            className="mt-4 text-brand-400 hover:text-brand-300 font-medium"
                        >
                            Create your first override →
                        </button>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="data-table">
                            <thead>
                                <tr className="bg-surface-800/50">
                                    <th>Audio ID</th>
                                    <th>Safety Score</th>
                                    <th>Fraud Flag</th>
                                    <th>Category Tags</th>
                                    <th>Reason</th>
                                    <th>Created</th>
                                    <th className="text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {overrides.map((override) => (
                                    <tr key={override.audio_id}>
                                        <td className="font-mono text-brand-400">{override.audio_id}</td>
                                        <td><StatusBadge score={override.brand_safety_score} /></td>
                                        <td>
                                            {override.fraud_flag ? (
                                                <span className="text-danger flex items-center gap-1">
                                                    <AlertTriangle className="w-4 h-4" />
                                                    Yes
                                                </span>
                                            ) : (
                                                <span className="text-surface-500">No</span>
                                            )}
                                        </td>
                                        <td>
                                            <div className="flex flex-wrap gap-1">
                                                {override.category_tags.slice(0, 3).map((tag) => (
                                                    <span
                                                        key={tag}
                                                        className="px-2 py-0.5 rounded text-xs bg-surface-700 text-surface-300"
                                                    >
                                                        {tag}
                                                    </span>
                                                ))}
                                                {override.category_tags.length > 3 && (
                                                    <span className="text-xs text-surface-500">
                                                        +{override.category_tags.length - 3}
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="max-w-xs truncate text-surface-400">
                                            {override.reason || '-'}
                                        </td>
                                        <td className="text-surface-400 text-xs">
                                            {formatDate(override.created_at)}
                                        </td>
                                        <td className="text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => openEditModal(override)}
                                                    className="p-2 rounded-lg hover:bg-surface-700 transition-colors"
                                                    title="Edit"
                                                >
                                                    <Pencil className="w-4 h-4 text-surface-400" />
                                                </button>
                                                <button
                                                    onClick={() => setDeleteConfirm(override.audio_id)}
                                                    className="p-2 rounded-lg hover:bg-danger/20 transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-4 h-4 text-danger" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Add/Edit Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    {/* Backdrop */}
                    <div
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={() => setIsModalOpen(false)}
                    />

                    {/* Modal */}
                    <div className="relative glass-card w-full max-w-lg p-6 space-y-6">
                        <div className="flex items-center justify-between">
                            <h3 className="text-xl font-bold text-white">
                                {editingOverride ? 'Edit Override' : 'New Override'}
                            </h3>
                            <button
                                onClick={() => setIsModalOpen(false)}
                                className="p-2 rounded-lg hover:bg-surface-700 transition-colors"
                            >
                                <X className="w-5 h-5 text-surface-400" />
                            </button>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Audio ID */}
                            <div>
                                <label className="block text-sm font-medium text-surface-300 mb-2">
                                    Audio ID
                                </label>
                                <input
                                    type="text"
                                    value={formData.audio_id}
                                    onChange={(e) => setFormData({ ...formData, audio_id: e.target.value })}
                                    className="input-field"
                                    placeholder="e.g., audio_12345"
                                    disabled={!!editingOverride}
                                    required
                                />
                            </div>

                            {/* Brand Safety Score */}
                            <div>
                                <label className="block text-sm font-medium text-surface-300 mb-2">
                                    Brand Safety Score
                                </label>
                                <select
                                    value={formData.brand_safety_score}
                                    onChange={(e) => setFormData({
                                        ...formData,
                                        brand_safety_score: e.target.value as BrandSafetyScore
                                    })}
                                    className="select-field"
                                >
                                    <option value="SAFE">SAFE</option>
                                    <option value="RISK_MEDIUM">RISK_MEDIUM</option>
                                    <option value="RISK_HIGH">RISK_HIGH</option>
                                    <option value="UNKNOWN">UNKNOWN</option>
                                </select>
                            </div>

                            {/* Fraud Flag */}
                            <div className="flex items-center gap-3">
                                <input
                                    type="checkbox"
                                    id="fraud_flag"
                                    checked={formData.fraud_flag}
                                    onChange={(e) => setFormData({ ...formData, fraud_flag: e.target.checked })}
                                    className="w-5 h-5 rounded border-surface-600 bg-surface-800 text-brand-500 focus:ring-brand-500"
                                />
                                <label htmlFor="fraud_flag" className="text-sm text-surface-300">
                                    Flag as Fraudulent Content
                                </label>
                            </div>

                            {/* Category Tags */}
                            <div>
                                <label className="block text-sm font-medium text-surface-300 mb-2">
                                    Category Tags (comma-separated)
                                </label>
                                <input
                                    type="text"
                                    value={formData.category_tags}
                                    onChange={(e) => setFormData({ ...formData, category_tags: e.target.value })}
                                    className="input-field"
                                    placeholder="e.g., news, politics, controversial"
                                />
                            </div>

                            {/* Reason */}
                            <div>
                                <label className="block text-sm font-medium text-surface-300 mb-2">
                                    Reason for Override
                                </label>
                                <textarea
                                    value={formData.reason}
                                    onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                                    className="input-field min-h-[80px] resize-none"
                                    placeholder="Explain why this override was created..."
                                />
                            </div>

                            {/* Submit */}
                            <div className="flex gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setIsModalOpen(false)}
                                    className="btn-secondary flex-1"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isSubmitting || !formData.audio_id}
                                    className="btn-glow flex-1 flex items-center justify-center gap-2"
                                >
                                    {isSubmitting ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            <CheckCircle className="w-5 h-5" />
                                            {editingOverride ? 'Update' : 'Create'}
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deleteConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={() => setDeleteConfirm(null)}
                    />
                    <div className="relative glass-card w-full max-w-sm p-6 space-y-6 text-center">
                        <div className="w-16 h-16 rounded-full bg-danger/20 flex items-center justify-center mx-auto">
                            <Trash2 className="w-8 h-8 text-danger" />
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-white mb-2">Delete Override?</h3>
                            <p className="text-surface-400">
                                Are you sure you want to delete the override for{' '}
                                <span className="font-mono text-brand-400">{deleteConfirm}</span>?
                                This action cannot be undone.
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setDeleteConfirm(null)}
                                className="btn-secondary flex-1"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => handleDelete(deleteConfirm)}
                                className="btn-danger flex-1"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
