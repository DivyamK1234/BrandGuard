/**
 * Next.js API Route: Admin Override by ID Proxy
 * 
 * Proxies update and delete requests for specific audio overrides.
 */

import { NextRequest, NextResponse } from 'next/server'

const getBackendUrl = () => process.env.BACKEND_URL || 'http://localhost:8000'

// PUT - Update override
export async function PUT(
    request: NextRequest,
    context: { params: Promise<{ audio_id: string }> }
) {
    try {
        const { audio_id } = await context.params
        const body = await request.json()
        
        const response = await fetch(`${getBackendUrl()}/api/v1/admin/override/${audio_id}`, {
            method: 'PUT',
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
        console.error('Admin override PUT error:', error)
        return NextResponse.json(
            { error: 'Failed to update override' },
            { status: 500 }
        )
    }
}

// DELETE - Delete override
export async function DELETE(
    request: NextRequest,
    context: { params: Promise<{ audio_id: string }> }
) {
    try {
        const { audio_id } = await context.params
        
        const response = await fetch(`${getBackendUrl()}/api/v1/admin/override/${audio_id}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
        })

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
            return NextResponse.json(errorData, { status: response.status })
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error('Admin override DELETE error:', error)
        return NextResponse.json(
            { error: 'Failed to delete override' },
            { status: 500 }
        )
    }
}
