import { chromium, type Browser } from "playwright"

import {
  normalizeCardRenderPayload,
  type CardRenderViewport,
} from "./payload"

let browserPromise: Promise<Browser> | null = null

async function getBrowser(): Promise<Browser> {
  if (!browserPromise) {
    browserPromise = chromium.launch({
      headless: true,
    })
  }

  try {
    return await browserPromise
  } catch (error) {
    browserPromise = null
    throw error
  }
}

function normalizeOrigin(origin: string): string {
  const trimmed = origin.trim().replace(/\/+$/, "")
  if (trimmed.length === 0) {
    throw new Error("Render origin must be a non-empty URL")
  }
  return trimmed
}

function buildTemplateUrl(origin: string, payload: unknown): string {
  const rawPayload = JSON.stringify(payload)
  const encodedPayload = encodeURIComponent(rawPayload)
  return `${origin}/templates/daily?payload=${encodedPayload}`
}

export async function renderCardPng(
  input: unknown,
  options?: {
    origin?: string
    timeoutMs?: number
    viewport?: CardRenderViewport
  },
): Promise<Buffer> {
  const payload = normalizeCardRenderPayload(input)
  const origin = normalizeOrigin(options?.origin ?? "")
  const timeoutMs = Math.max(1000, Math.min(options?.timeoutMs ?? 15000, 15000))
  const viewport = options?.viewport ?? {
    width: 1200,
    height: 1600,
    deviceScaleFactor: 2,
  }
  const { width, height, deviceScaleFactor } = viewport
  const browser = await getBrowser()
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor,
  })

  try {
    page.setDefaultTimeout(timeoutMs)
    page.setDefaultNavigationTimeout(timeoutMs)
    await page.goto(buildTemplateUrl(origin, payload), {
      waitUntil: "networkidle",
      timeout: timeoutMs,
    })
    const card = page.locator("[data-card-root]").first()
    await card.waitFor({ state: "visible", timeout: timeoutMs })
    const image = await card.screenshot({
      type: "png",
      timeout: timeoutMs,
    })
    return Buffer.from(image)
  } finally {
    await page.close().catch(() => undefined)
  }
}
