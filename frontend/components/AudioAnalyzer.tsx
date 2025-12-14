'use client'

/**
 * AudioAnalyzer Component
 * 
 * The "Spotify" experience for audio safety verification.
 * 
 * Features:
 * - MP3 file upload with drag-and-drop
 * - wavesurfer.js integration for audio visualization
 * - Regions plugin for marking unsafe content segments
 * - Real-time API integration with /api/v1/verify_audio
 * 
 * Reference: ADVERIFY-UI-2 - Service Health Dashboard (adapted for demo client)
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import {
    Upload,
    Play,
    Pause,
    Volume2,
    VolumeX,
    AlertTriangle,
    CheckCircle,
    AlertCircle,
    HelpCircle,
    Loader2,
    Music,
    Clock,
    Tag,
    Shield
} from 'lucide-react'
import { clsx } from 'clsx'

// Simple hash function for generating consistent audio IDs
function hashString(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(36);
}

// Types for verification result (matches backend models.py)
interface UnsafeSegment {
    start?: number
    end?: number
    start_time?: string  // "MM:SS" format
    end_time?: string    // "MM:SS" format
    reason: string
}

interface VerificationResult {
    audio_id: string
    brand_safety_score: 'SAFE' | 'RISK_HIGH' | 'RISK_MEDIUM' | 'UNKNOWN'
    fraud_flag: boolean
    category_tags: string[]
    source: 'MANUAL_OVERRIDE' | 'CACHE' | 'AI_GENERATED'
    confidence_score: number | null
    unsafe_segments: UnsafeSegment[] | null
    transcript_snippet: string | null
    content_summary: string | null
    created_at: string
}

// WaveSurfer types
interface WaveSurferInstance {
    on: (event: string, callback: (...args: unknown[]) => void) => void
    play: () => void
    pause: () => void
    stop: () => void
    destroy: () => void
    loadBlob: (blob: Blob) => void
    getDuration: () => number
    getCurrentTime: () => number
    setVolume: (volume: number) => void
    getVolume: () => number
    isPlaying: () => boolean
}

interface RegionParams {
    start: number
    end: number
    color: string
    content?: string
}

interface RegionsPluginInstance {
    addRegion: (params: RegionParams) => void
    clearRegions: () => void
}

export default function AudioAnalyzer() {
    // State
    const [file, setFile] = useState<File | null>(null)
    const [audioUrl, setAudioUrl] = useState<string>('')
    const [inputMode, setInputMode] = useState<'file' | 'url'>('url')
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [result, setResult] = useState<VerificationResult | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isPlaying, setIsPlaying] = useState(false)
    const [isMuted, setIsMuted] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [isDragging, setIsDragging] = useState(false)
    const [progress, setProgress] = useState(0)
    const [statusMessage, setStatusMessage] = useState('')

    // Refs
    const waveformRef = useRef<HTMLDivElement>(null)
    const wavesurferRef = useRef<WaveSurferInstance | null>(null)
    const regionsRef = useRef<RegionsPluginInstance | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Initialize WaveSurfer
    useEffect(() => {
        if (typeof window === 'undefined') return

        const initWaveSurfer = async () => {
            const WaveSurfer = (await import('wavesurfer.js')).default
            const RegionsPlugin = (await import('wavesurfer.js/dist/plugins/regions.js')).default

            if (waveformRef.current && !wavesurferRef.current) {
                const regions = RegionsPlugin.create() as unknown as RegionsPluginInstance
                regionsRef.current = regions

                wavesurferRef.current = WaveSurfer.create({
                    container: waveformRef.current,
                    waveColor: '#64748b',
                    progressColor: '#0ea5e9',
                    cursorColor: '#38bdf8',
                    barWidth: 2,
                    barGap: 1,
                    barRadius: 2,
                    height: 128,
                    normalize: true,
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    plugins: [regions as any],
                }) as unknown as WaveSurferInstance

                wavesurferRef.current.on('ready', () => {
                    setDuration(wavesurferRef.current?.getDuration() || 0)
                })

                wavesurferRef.current.on('audioprocess', () => {
                    setCurrentTime(wavesurferRef.current?.getCurrentTime() || 0)
                })

                wavesurferRef.current.on('play', () => setIsPlaying(true))
                wavesurferRef.current.on('pause', () => setIsPlaying(false))
                wavesurferRef.current.on('finish', () => setIsPlaying(false))
            }
        }

        initWaveSurfer()

        return () => {
            if (wavesurferRef.current) {
                wavesurferRef.current.destroy()
                wavesurferRef.current = null
            }
        }
    }, [])

    // Load audio file into WaveSurfer
    useEffect(() => {
        if (file && wavesurferRef.current) {
            wavesurferRef.current.loadBlob(file)
            setResult(null)
            setError(null)
        }
    }, [file])

    // Add regions when result is received
    useEffect(() => {
        if (result?.unsafe_segments && regionsRef.current) {
            // Clear existing regions
            regionsRef.current.clearRegions()

            // Add red regions for unsafe segments
            result.unsafe_segments.forEach((segment) => {
                // Helper to parse MM:SS string if numeric start/end are missing
                const parseTimeStr = (str?: string) => {
                    if (!str) return 0;
                    const parts = str.split(':').map(Number);
                    if (parts.length === 2) return parts[0] * 60 + parts[1]; // MM:SS
                    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]; // HH:MM:SS
                    return 0;
                };

                const start = segment.start ?? parseTimeStr(segment.start_time);
                const end = segment.end ?? parseTimeStr(segment.end_time);

                // Only add region if we have valid times
                if (end > start) {
                    regionsRef.current?.addRegion({
                        start,
                        end,
                        color: 'rgba(239, 68, 68, 0.3)',
                        content: segment.reason,
                    })
                }
            })
        }
    }, [result])

    // File drop handlers
    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)

        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile && droppedFile.type.startsWith('audio/')) {
            setFile(droppedFile)
        } else {
            setError('Please upload an audio file (MP3, WAV, etc.)')
        }
    }, [])

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0]
        if (selectedFile) {
            setFile(selectedFile)
        }
    }, [])

    // Analyze audio
    const analyzeAudio = async () => {
        if (inputMode === 'file' && !file) return
        if (inputMode === 'url' && !audioUrl.trim()) return

        setIsAnalyzing(true)
        setError(null)
        setProgress(0)
        setStatusMessage('Starting analysis...')

        try {
            if (inputMode === 'file' && file) {
                // File upload mode - synchronous
                const formData = new FormData()
                formData.append('audio_file', file)
                formData.append('audio_id', `upload_${hashString(file.name + file.size)}`)

                setStatusMessage('Uploading and analyzing...')
                setProgress(30)

                const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/verify_audio`, {
                    method: 'POST',
                    body: formData,
                })

                if (!response.ok) {
                    throw new Error(`API error: ${response.status}`)
                }

                const data: VerificationResult = await response.json()
                setResult(data)
                setProgress(100)
                setStatusMessage('Complete!')
            } else {
                // URL mode - use async processing with polling
                setStatusMessage('Submitting job...')

                const submitResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/verify_audio_async`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        audio_url: audioUrl.trim(),
                        audio_id: `url_${hashString(audioUrl.trim())}`,
                    }),
                })

                if (!submitResponse.ok) {
                    throw new Error(`API error: ${submitResponse.status}`)
                }

                const jobData = await submitResponse.json()

                // If cached, result is immediate
                if (jobData.status === 'complete' && jobData.result) {
                    setResult(jobData.result as VerificationResult)
                    setProgress(100)
                    setStatusMessage('Complete!')
                    return
                }

                // Poll for job status
                const jobId = jobData.job_id
                let attempts = 0
                const maxAttempts = 300 // 10 minutes max (2s intervals)

                while (attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 2000))

                    const statusResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/job/${jobId}`)
                    if (!statusResponse.ok) {
                        throw new Error('Failed to get job status')
                    }

                    const status = await statusResponse.json()
                    setProgress(status.progress || 0)
                    setStatusMessage(status.message || 'Processing...')

                    if (status.status === 'complete') {
                        setResult(status.result as VerificationResult)
                        setProgress(100)
                        setStatusMessage('Complete!')
                        return
                    }

                    if (status.status === 'failed') {
                        throw new Error(status.error || 'Analysis failed')
                    }

                    attempts++
                }

                throw new Error('Job timed out')
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Analysis failed')
            setProgress(0)
            setStatusMessage('')
        } finally {
            setIsAnalyzing(false)
        }
    }

    // Playback controls
    const togglePlay = () => {
        if (wavesurferRef.current) {
            if (isPlaying) {
                wavesurferRef.current.pause()
            } else {
                wavesurferRef.current.play()
            }
        }
    }

    const toggleMute = () => {
        if (wavesurferRef.current) {
            const newMuted = !isMuted
            wavesurferRef.current.setVolume(newMuted ? 0 : 1)
            setIsMuted(newMuted)
        }
    }

    // Format time
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    // Get status badge component
    const StatusBadge = ({ score }: { score: VerificationResult['brand_safety_score'] }) => {
        const config = {
            SAFE: {
                class: 'badge-safe',
                icon: <CheckCircle className="w-4 h-4" />,
                label: 'Safe'
            },
            RISK_MEDIUM: {
                class: 'badge-warning',
                icon: <AlertTriangle className="w-4 h-4" />,
                label: 'Risk Medium'
            },
            RISK_HIGH: {
                class: 'badge-danger',
                icon: <AlertCircle className="w-4 h-4" />,
                label: 'Risk High'
            },
            UNKNOWN: {
                class: 'badge-unknown',
                icon: <HelpCircle className="w-4 h-4" />,
                label: 'Unknown'
            },
        }

        const { class: badgeClass, icon, label } = config[score]

        return (
            <span className={clsx(badgeClass, 'flex items-center gap-1.5')}>
                {icon}
                {label}
            </span>
        )
    }

    return (
        <div className="space-y-6">
            {/* Input Mode Toggle */}
            <div className="flex gap-2 p-1 bg-surface-800/50 rounded-xl w-fit">
                <button
                    onClick={() => setInputMode('url')}
                    className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                        inputMode === 'url'
                            ? 'bg-brand-500 text-white'
                            : 'text-surface-400 hover:text-white'
                    )}
                >
                    Podcast URL
                </button>
                <button
                    onClick={() => setInputMode('file')}
                    className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                        inputMode === 'file'
                            ? 'bg-brand-500 text-white'
                            : 'text-surface-400 hover:text-white'
                    )}
                >
                    Upload File
                </button>
            </div>

            {/* URL Input */}
            {inputMode === 'url' && (
                <div className="glass-card p-6">
                    <label className="block text-sm font-medium text-surface-300 mb-2">
                        Enter Audio or YouTube URL
                    </label>
                    <input
                        type="url"
                        value={audioUrl}
                        onChange={(e) => setAudioUrl(e.target.value)}
                        placeholder="https://youtube.com/watch?v=... or https://example.com/podcast.mp3"
                        className="w-full px-4 py-3 bg-surface-800/50 border border-surface-700 rounded-xl text-white placeholder-surface-500 focus:outline-none focus:border-brand-500 transition-colors"
                    />
                    <p className="text-xs text-surface-500 mt-2">
                        ✅ YouTube • SoundCloud • Twitter/X • TikTok • Vimeo • RSS feeds • MP3 URLs
                    </p>
                    <button
                        onClick={analyzeAudio}
                        disabled={isAnalyzing || !audioUrl.trim()}
                        className="btn-glow flex items-center gap-2 mt-4"
                    >
                        {isAnalyzing ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Analyzing...
                            </>
                        ) : (
                            <>
                                <Shield className="w-5 h-5" />
                                Analyze URL for Safety
                            </>
                        )}
                    </button>

                    {/* Progress Bar */}
                    {isAnalyzing && (
                        <div className="mt-4">
                            <div className="flex justify-between text-sm text-surface-400 mb-2">
                                <span>{statusMessage}</span>
                                <span>{progress}%</span>
                            </div>
                            <div className="w-full bg-surface-700 rounded-full h-2 overflow-hidden">
                                <div
                                    className="bg-gradient-to-r from-brand-500 to-brand-400 h-full rounded-full transition-all duration-500 ease-out"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                            <p className="text-xs text-surface-500 mt-2">
                                Long podcasts may take 2-5 minutes to download and analyze
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* File Upload Area */}
            {inputMode === 'file' && (
                <div
                    className={clsx(
                        'glass-card p-8 border-2 border-dashed transition-all duration-300',
                        isDragging
                            ? 'border-brand-500 bg-brand-500/10'
                            : 'border-surface-600 hover:border-surface-500',
                        'cursor-pointer'
                    )}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="audio/*"
                        onChange={handleFileSelect}
                        className="hidden"
                    />

                    <div className="flex flex-col items-center gap-4 text-center">
                        <div className={clsx(
                            'w-16 h-16 rounded-2xl flex items-center justify-center transition-all',
                            file ? 'bg-brand-500/20' : 'bg-surface-800',
                            isDragging && 'scale-110'
                        )}>
                            {file ? (
                                <Music className="w-8 h-8 text-brand-400" />
                            ) : (
                                <Upload className="w-8 h-8 text-surface-400" />
                            )}
                        </div>

                        {file ? (
                            <div>
                                <p className="text-lg font-semibold text-white">{file.name}</p>
                                <p className="text-sm text-surface-400">
                                    {(file.size / 1024 / 1024).toFixed(2)} MB
                                </p>
                            </div>
                        ) : (
                            <div>
                                <p className="text-lg font-semibold text-white">
                                    Drop your audio file here
                                </p>
                                <p className="text-sm text-surface-400">
                                    or click to browse • MP3, WAV, M4A supported
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Waveform Player */}
            {file && (
                <div className="glass-card p-6 space-y-4">
                    <div className="waveform-container p-4">
                        <div ref={waveformRef} />
                    </div>

                    {/* Playback controls */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={togglePlay}
                                className="w-12 h-12 rounded-full bg-brand-600 hover:bg-brand-500 flex items-center justify-center transition-colors"
                            >
                                {isPlaying ? (
                                    <Pause className="w-5 h-5 text-white" />
                                ) : (
                                    <Play className="w-5 h-5 text-white ml-0.5" />
                                )}
                            </button>

                            <button
                                onClick={toggleMute}
                                className="w-10 h-10 rounded-full bg-surface-700 hover:bg-surface-600 flex items-center justify-center transition-colors"
                            >
                                {isMuted ? (
                                    <VolumeX className="w-5 h-5 text-surface-300" />
                                ) : (
                                    <Volume2 className="w-5 h-5 text-surface-300" />
                                )}
                            </button>

                            <span className="text-sm text-surface-400">
                                {formatTime(currentTime)} / {formatTime(duration)}
                            </span>
                        </div>

                        <button
                            onClick={analyzeAudio}
                            disabled={isAnalyzing}
                            className="btn-glow flex items-center gap-2"
                        >
                            {isAnalyzing ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Analyzing...
                                </>
                            ) : (
                                <>
                                    <Shield className="w-5 h-5" />
                                    Analyze for Safety
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}

            {/* Error message */}
            {error && (
                <div className="glass-card p-4 border border-danger/30 bg-danger/10">
                    <div className="flex items-center gap-3 text-danger">
                        <AlertCircle className="w-5 h-5" />
                        <span>{error}</span>
                    </div>
                </div>
            )}

            {/* Results */}
            {result && (
                <div className="glass-card p-6 space-y-6">
                    <div className="flex items-center justify-between">
                        <h3 className="text-xl font-bold text-white">Analysis Results</h3>
                        <StatusBadge score={result.brand_safety_score} />
                    </div>

                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Left column - Details */}
                        <div className="space-y-4">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center">
                                    <Tag className="w-5 h-5 text-brand-400" />
                                </div>
                                <div>
                                    <p className="text-sm text-surface-400">Audio ID</p>
                                    <p className="text-white font-mono">{result.audio_id}</p>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center">
                                    <Clock className="w-5 h-5 text-brand-400" />
                                </div>
                                <div>
                                    <p className="text-sm text-surface-400">Source</p>
                                    <p className="text-white">{result.source.replace('_', ' ')}</p>
                                </div>
                            </div>

                            {result.confidence_score !== null && (
                                <div>
                                    <p className="text-sm text-surface-400 mb-2">Confidence Score</p>
                                    <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-brand-600 to-brand-400 transition-all duration-500"
                                            style={{ width: `${result.confidence_score * 100}%` }}
                                        />
                                    </div>
                                    <p className="text-sm text-surface-400 mt-1">
                                        {(result.confidence_score * 100).toFixed(1)}%
                                    </p>
                                </div>
                            )}

                            <div>
                                <p className="text-sm text-surface-400 mb-2">Category Tags</p>
                                <div className="flex flex-wrap gap-2">
                                    {result.category_tags.map((tag) => (
                                        <span
                                            key={tag}
                                            className="px-3 py-1 rounded-full text-xs font-medium bg-surface-800 text-surface-300 border border-surface-700"
                                        >
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {result.fraud_flag && (
                                <div className="flex items-center gap-2 text-danger">
                                    <AlertTriangle className="w-5 h-5" />
                                    <span className="font-medium">Fraud Flag Detected</span>
                                </div>
                            )}
                        </div>

                        {/* Right column - Summary & Unsafe Timestamps */}
                        <div className="space-y-4">
                            {/* Content Summary */}
                            {result.content_summary && (
                                <div>
                                    <p className="text-sm text-surface-400 mb-2">📋 Content Summary</p>
                                    <div className="p-4 bg-surface-800/50 rounded-xl border border-surface-700">
                                        <p className="text-sm text-white">
                                            {result.content_summary}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Unsafe Ad Segments */}
                            {result.unsafe_segments && result.unsafe_segments.length > 0 && (
                                <div>
                                    <p className="text-sm text-danger mb-2">
                                        🚫 Unsafe Ad Timestamps ({result.unsafe_segments.length})
                                    </p>
                                    <div className="space-y-2 max-h-60 overflow-y-auto">
                                        {result.unsafe_segments.map((segment, idx) => (
                                            <div
                                                key={idx}
                                                className="p-3 bg-danger/10 rounded-lg border border-danger/20"
                                            >
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="px-2 py-0.5 bg-danger/20 rounded text-xs text-danger font-mono font-bold">
                                                        {segment.start_time || formatTime(segment.start || 0)} - {segment.end_time || formatTime(segment.end || 0)}
                                                    </span>
                                                </div>
                                                <p className="text-sm text-surface-300">{segment.reason}</p>
                                            </div>
                                        ))}
                                    </div>
                                    <p className="text-xs text-surface-500 mt-2">
                                        ⚠️ Do not show ads during these timestamps
                                    </p>
                                </div>
                            )}

                            {result.unsafe_segments?.length === 0 && (
                                <div className="p-4 bg-safe/10 rounded-xl border border-safe/20">
                                    <p className="text-sm text-safe">
                                        ✅ No unsafe segments detected - ads can run throughout
                                    </p>
                                </div>
                            )}


                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
