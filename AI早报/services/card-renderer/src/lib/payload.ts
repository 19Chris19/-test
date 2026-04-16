export interface CardArticlePayload {
  article_id: number
  section: string
  rank: number
  title: string
  url: string
  rendered_summary: string
  source_url: string
  dedupe_key: string
  article_score: number
}

export interface CardSectionPayload {
  name: string
  articles: CardArticlePayload[]
}

export interface CardIssueMeta {
  issue_id: number
  issue_number: number
  report_date: string
  title: string
  status: string
  markdown_path: string
  github_url: string
  published_at: string | null
  article_count: number
  backup_filename: string
}

export interface CardRenderPayload {
  issue: CardIssueMeta
  sections: CardSectionPayload[]
  featured_articles: CardArticlePayload[]
  layout_hint: string
  schema_version: string
}

export interface CardRenderViewport {
  width: number
  height: number
  deviceScaleFactor: number
}

export interface CardRenderRequest {
  payload: CardRenderPayload
  viewport: CardRenderViewport
  timeoutMs: number
}

interface RawCardRenderRequest extends Record<string, unknown> {
  payload: unknown
  viewport?: unknown
  timeoutMs?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function requireRecord(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new Error(`${label} must be an object`)
  }
  return value
}

function requireString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${label} must be a non-empty string`)
  }
  return value.trim()
}

function requireNumber(value: unknown, label: string): number {
  const candidate =
    typeof value === "number" ? value : typeof value === "string" ? Number(value) : Number.NaN
  if (!Number.isFinite(candidate)) {
    throw new Error(`${label} must be a finite number`)
  }
  return candidate
}

function requireInteger(value: unknown, label: string): number {
  return Math.trunc(requireNumber(value, label))
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function normalizeArticle(value: unknown, fallbackSection: string): CardArticlePayload {
  const article = requireRecord(value, "article")
  return {
    article_id: requireInteger(article.article_id, "article.article_id"),
    section: requireString(article.section ?? fallbackSection, "article.section"),
    rank: requireInteger(article.rank, "article.rank"),
    title: requireString(article.title, "article.title"),
    url: requireString(article.url, "article.url"),
    rendered_summary: requireString(
      article.rendered_summary ?? "待补充摘要",
      "article.rendered_summary",
    ),
    source_url: requireString(article.source_url ?? article.url, "article.source_url"),
    dedupe_key: requireString(article.dedupe_key, "article.dedupe_key"),
    article_score: requireNumber(article.article_score ?? 0, "article.article_score"),
  }
}

function normalizeArticles(
  value: unknown,
  fallbackSection: string,
  label: string,
): CardArticlePayload[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`)
  }
  return value.map((item, index) => {
    try {
      return normalizeArticle(item, fallbackSection)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      throw new Error(`${label}[${index}]: ${message}`)
    }
  })
}

function normalizeSection(value: unknown, index: number): CardSectionPayload {
  const section = requireRecord(value, `sections[${index}]`)
  const name = requireString(section.name, `sections[${index}].name`)
  return {
    name,
    articles: normalizeArticles(section.articles, name, `sections[${index}].articles`),
  }
}

function normalizeIssueMeta(value: unknown): CardIssueMeta {
  const issue = requireRecord(value, "issue")
  return {
    issue_id: requireInteger(issue.issue_id, "issue.issue_id"),
    issue_number: requireInteger(issue.issue_number, "issue.issue_number"),
    report_date: requireString(issue.report_date, "issue.report_date"),
    title: requireString(issue.title, "issue.title"),
    status: requireString(issue.status, "issue.status"),
    markdown_path: requireString(issue.markdown_path, "issue.markdown_path"),
    github_url: requireString(issue.github_url, "issue.github_url"),
    published_at:
      typeof issue.published_at === "string" && issue.published_at.trim().length > 0
        ? issue.published_at.trim()
        : null,
    article_count: requireInteger(issue.article_count, "issue.article_count"),
    backup_filename: requireString(issue.backup_filename, "issue.backup_filename"),
  }
}

function normalizeViewport(value: unknown): CardRenderViewport {
  const viewport = isRecord(value) ? value : {}
  return {
    width: clamp(requireInteger(viewport.width ?? 1200, "viewport.width"), 640, 1920),
    height: clamp(requireInteger(viewport.height ?? 1600, "viewport.height"), 960, 2400),
    deviceScaleFactor: clamp(
      requireNumber(viewport.deviceScaleFactor ?? 2, "viewport.deviceScaleFactor"),
      1,
      3,
    ),
  }
}

export function normalizeCardRenderPayload(input: unknown): CardRenderPayload {
  const candidate = isRecord(input) && "issue" in input ? input : requireRecord(input, "payload")
  const issue = normalizeIssueMeta(candidate.issue)
  const sections = candidate.sections
  const featuredArticles = candidate.featured_articles

  if (!Array.isArray(sections) || sections.length === 0) {
    throw new Error("payload.sections must contain at least one section")
  }
  if (!Array.isArray(featuredArticles)) {
    throw new Error("payload.featured_articles must be an array")
  }

  return {
    issue,
    sections: sections.map((section, index) => normalizeSection(section, index)),
    featured_articles: normalizeArticles(featuredArticles, "featured", "featured_articles"),
    layout_hint: requireString(candidate.layout_hint ?? "poster", "payload.layout_hint"),
    schema_version: requireString(
      candidate.schema_version ?? "card-render.v1",
      "payload.schema_version",
    ),
  }
}

export function normalizeCardRenderRequest(input: unknown): CardRenderRequest {
  const request: RawCardRenderRequest = isRecord(input) && "payload" in input
    ? (input as RawCardRenderRequest)
    : { payload: input }
  const timeoutMs =
    typeof request.timeoutMs === "number" || typeof request.timeoutMs === "string"
      ? clamp(requireInteger(request.timeoutMs, "timeoutMs"), 1000, 15000)
      : 15000

  return {
    payload: normalizeCardRenderPayload(request.payload),
    viewport: normalizeViewport(request.viewport),
    timeoutMs,
  }
}

export function createDemoCardRenderPayload(): CardRenderPayload {
  return {
    issue: {
      issue_id: 1,
      issue_number: 1,
      report_date: "2026-04-16",
      title: "AI 早报 2026-04-16",
      status: "published",
      markdown_path: "BACKUP/issue_1.md",
      github_url: "https://github.com/example/repo/issues/1",
      published_at: "2026-04-16T08:00:00+08:00",
      article_count: 4,
      backup_filename: "issue_1.md",
    },
    sections: [
      {
        name: "模型发布",
        articles: [
          {
            article_id: 1,
            section: "模型发布",
            rank: 1,
            title: "Nova-4 发布",
            url: "https://example.com/nova-4",
            rendered_summary: "新一代多模态模型，强调推理和工具调用。",
            source_url: "https://example.com/nova-4",
            dedupe_key: "demo-nova-4",
            article_score: 98.5,
          },
          {
            article_id: 2,
            section: "模型发布",
            rank: 2,
            title: "Open weight 系列更新",
            url: "https://example.com/open-weight",
            rendered_summary: "开源权重版本同步开放，适合本地部署与二次微调。",
            source_url: "https://example.com/open-weight",
            dedupe_key: "demo-open-weight",
            article_score: 95.2,
          },
        ],
      },
      {
        name: "开发工具",
        articles: [
          {
            article_id: 3,
            section: "开发工具",
            rank: 1,
            title: "Agent CLI 增强",
            url: "https://example.com/agent-cli",
            rendered_summary: "命令行入口新增批量执行、故障回溯和审计导出。",
            source_url: "https://example.com/agent-cli",
            dedupe_key: "demo-agent-cli",
            article_score: 92.1,
          },
          {
            article_id: 4,
            section: "开发工具",
            rank: 2,
            title: "Render Sandbox",
            url: "https://example.com/render-sandbox",
            rendered_summary: "新的渲染沙箱将前端截图链路从主流程中隔离出去。",
            source_url: "https://example.com/render-sandbox",
            dedupe_key: "demo-render-sandbox",
            article_score: 90.7,
          },
        ],
      },
    ],
    featured_articles: [
      {
        article_id: 1,
        section: "模型发布",
        rank: 1,
        title: "Nova-4 发布",
        url: "https://example.com/nova-4",
        rendered_summary: "新一代多模态模型，强调推理和工具调用。",
        source_url: "https://example.com/nova-4",
        dedupe_key: "demo-nova-4",
        article_score: 98.5,
      },
      {
        article_id: 3,
        section: "开发工具",
        rank: 1,
        title: "Agent CLI 增强",
        url: "https://example.com/agent-cli",
        rendered_summary: "命令行入口新增批量执行、故障回溯和审计导出。",
        source_url: "https://example.com/agent-cli",
        dedupe_key: "demo-agent-cli",
        article_score: 92.1,
      },
      {
        article_id: 4,
        section: "开发工具",
        rank: 2,
        title: "Render Sandbox",
        url: "https://example.com/render-sandbox",
        rendered_summary: "新的渲染沙箱将前端截图链路从主流程中隔离出去。",
        source_url: "https://example.com/render-sandbox",
        dedupe_key: "demo-render-sandbox",
        article_score: 90.7,
      },
    ],
    layout_hint: "poster",
    schema_version: "card-render.v1",
  }
}
