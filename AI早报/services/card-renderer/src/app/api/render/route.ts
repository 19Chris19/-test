import { NextResponse } from "next/server"

import { normalizeCardRenderRequest } from "../../../lib/payload"
import { renderCardPng } from "../../../lib/playwright"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"
export const maxDuration = 15

const MAX_CONCURRENT_RENDER_JOBS = 2
const MAX_QUEUE_DEPTH = 4
const HARD_TIMEOUT_MS = 15_000

let activeRenderJobs = 0
const waitQueue: Array<() => void> = []

async function acquireRenderSlot() {
  if (activeRenderJobs < MAX_CONCURRENT_RENDER_JOBS) {
    activeRenderJobs += 1
    return
  }

  if (waitQueue.length >= MAX_QUEUE_DEPTH) {
    throw new Error("Render queue is full")
  }

  await new Promise<void>((resolve) => {
    waitQueue.push(resolve)
  })
  activeRenderJobs += 1
}

function releaseRenderSlot() {
  activeRenderJobs = Math.max(0, activeRenderJobs - 1)
  const next = waitQueue.shift()
  next?.()
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return String(error)
}

function jsonError(message: string, status: number) {
  return NextResponse.json(
    {
      ok: false,
      error: message,
    },
    {
      status,
    },
  )
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "card-renderer",
    endpoint: "POST /api/render",
    timeout_ms: HARD_TIMEOUT_MS,
    max_concurrency: MAX_CONCURRENT_RENDER_JOBS,
    schema_version: "card-render.v1",
  })
}

export async function POST(request: Request) {
  const startedAt = Date.now()
  const requestOrigin = new URL(request.url).origin
  let rawBody: unknown

  try {
    rawBody = await request.json()
  } catch (error) {
    return jsonError(`Invalid JSON body: ${errorMessage(error)}`, 400)
  }

  let normalized
  try {
    normalized = normalizeCardRenderRequest(rawBody)
  } catch (error) {
    return jsonError(`Invalid render payload: ${errorMessage(error)}`, 400)
  }

  if (normalized.timeoutMs > HARD_TIMEOUT_MS) {
    normalized.timeoutMs = HARD_TIMEOUT_MS
  }

  try {
    await acquireRenderSlot()
  } catch (error) {
    return jsonError(errorMessage(error), 429)
  }

  try {
    const png = await renderCardPng(normalized.payload, {
      origin: requestOrigin,
      timeoutMs: normalized.timeoutMs,
      viewport: normalized.viewport,
    })
    return new Response(new Uint8Array(png), {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "image/png",
        "X-AI-Daily-Render-Ms": String(Date.now() - startedAt),
        "X-AI-Daily-Schema": normalized.payload.schema_version,
        "X-AI-Daily-Issue": String(normalized.payload.issue.issue_number),
      },
    })
  } catch (error) {
    return jsonError(`Render failed: ${errorMessage(error)}`, 500)
  } finally {
    releaseRenderSlot()
  }
}
