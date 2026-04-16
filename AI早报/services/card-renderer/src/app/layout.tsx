import type { ReactNode } from "react"

import "./globals.css"

export const metadata = {
  title: "AI 早报 card-renderer",
  description: "Single-purpose visual renderer for AI 早报 issue cards.",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
