/**
 * Next.js API Route: Admin Override Proxy
 * 
 * Proxies all admin override requests to the backend.
 * Supports GET (list), POST (create), PUT (update), DELETE operations.
 */

import { NextRequest, NextResponse } from 'next/server'

const getBackendUrl = () => process.env.BACKEND_URL || 'http://localhost:8000'

// GET - List overrides
export async function GET(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url)
        const queryString = searchParams.toString()
        
        const url = `${getBackendUrl()}/api/v1/admin/override${queryString ? `?${queryString}` : ''}`
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            cache: 'no-store',
        })

        if (!response.ok) {
            throw new Error(`Backend returned ${response.status}`)
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error('Admin override GET error:', error)
        return NextResponse.json(
            { error: 'Failed to fetch overrides from backend' },
            { status: 500 }
        )
    }
}

// POST - Create override
export async function POST(request: NextRequest) {
    try {
        const body = await request.json()
        
        const response = await fetch(`${getBackendUrl()}/api/v1/admin/override`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        })

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
            return NextResponse.json(errorData, { status: response.status })
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error('Admin override POST error:', error)
        return NextResponse.json(
            { error: 'Failed to create override' },
            { status: 500 }
        )
    }
}
