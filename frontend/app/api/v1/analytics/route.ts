/**
 * Next.js API Route: Analytics Proxy
 * 
 * This route proxies requests to the backend analytics endpoint.
 * Uses runtime environment variables to support Docker networking.
 */

import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
    try {
        // Use BACKEND_URL from environment (set in docker-compose.yaml)
        // In Docker: http://backend:8000
        // In local dev: http://localhost:8000
        const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
        
        const response = await fetch(`${backendUrl}/api/v1/analytics`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            // Disable caching for real-time data
            cache: 'no-store',
        })

        if (!response.ok) {
            throw new Error(`Backend returned ${response.status}`)
        }

        const data = await response.json()
        
        return NextResponse.json(data)
    } catch (error) {
        console.error('Analytics proxy error:', error)
        return NextResponse.json(
            { error: 'Failed to fetch analytics from backend' },
            { status: 500 }
        )
    }
}
