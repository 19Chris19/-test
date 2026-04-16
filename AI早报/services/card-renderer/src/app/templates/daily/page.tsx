import {
  createDemoCardRenderPayload,
  type CardArticlePayload,
  type CardRenderPayload,
  normalizeCardRenderPayload,
} from "../../../lib/payload"

type SearchParamValue = string | string[] | undefined
type SearchParams = Record<string, SearchParamValue>

const styles = `
  .card-shell {
    position: relative;
    width: 1200px;
    min-height: 1600px;
    padding: 56px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.18);
    background:
      radial-gradient(circle at 15% 10%, rgba(103, 232, 249, 0.16), transparent 28%),
      radial-gradient(circle at 88% 16%, rgba(167, 139, 250, 0.18), transparent 24%),
      linear-gradient(180deg, rgba(10, 18, 33, 0.98) 0%, rgba(5, 9, 18, 0.98) 100%);
    color: #eef4ff;
    box-shadow:
      0 32px 90px rgba(2, 6, 23, 0.58),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .card-shell::before,
  .card-shell::after {
    content: "";
    position: absolute;
    border-radius: 999px;
    filter: blur(40px);
    pointer-events: none;
  }

  .card-shell::before {
    left: -120px;
    top: 180px;
    width: 260px;
    height: 260px;
    background: rgba(103, 232, 249, 0.12);
  }

  .card-shell::after {
    right: -90px;
    bottom: 140px;
    width: 220px;
    height: 220px;
    background: rgba(167, 139, 250, 0.12);
  }

  .frame {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 28px;
  }

  .masthead {
    display: grid;
    gap: 18px;
    padding: 28px 30px 26px;
    border-radius: 28px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(10, 16, 30, 0.78));
    border: 1px solid rgba(148, 163, 184, 0.18);
    backdrop-filter: blur(12px);
  }

  .eyebrow {
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.24em;
    font-size: 12px;
    color: rgba(167, 243, 208, 0.9);
  }

  .title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }

  .headline {
    margin: 0;
    font-size: 52px;
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .lede {
    margin: 0;
    max-width: 760px;
    color: rgba(226, 232, 240, 0.84);
    font-size: 18px;
    line-height: 1.7;
  }

  .badge-row,
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: rgba(15, 23, 42, 0.72);
    color: rgba(226, 232, 240, 0.92);
    font-size: 13px;
    line-height: 1;
  }

  .badge strong {
    color: #ffffff;
    font-weight: 700;
  }

  .hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
    gap: 22px;
  }

  .spotlight,
  .stack-card,
  .section-card {
    border-radius: 26px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: rgba(9, 15, 28, 0.8);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }

  .spotlight {
    padding: 24px;
    display: grid;
    gap: 16px;
  }

  .spotlight-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }

  .spotlight-label {
    margin: 0;
    color: rgba(125, 211, 252, 0.9);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 12px;
  }

  .spotlight-title {
    margin: 0;
    font-size: 34px;
    line-height: 1.06;
    letter-spacing: -0.03em;
  }

  .spotlight-summary {
    margin: 0;
    color: rgba(226, 232, 240, 0.84);
    font-size: 17px;
    line-height: 1.72;
  }

  .stack {
    display: grid;
    gap: 16px;
  }

  .stack-card {
    padding: 20px;
    display: grid;
    gap: 12px;
  }

  .stack-card h3,
  .section-card h3 {
    margin: 0;
    font-size: 22px;
    line-height: 1.1;
  }

  .stack-card p,
  .section-card p {
    margin: 0;
    color: rgba(226, 232, 240, 0.78);
    line-height: 1.65;
  }

  .section-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
  }

  .section-card {
    padding: 22px;
    display: grid;
    gap: 14px;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
  }

  .section-head small {
    color: rgba(148, 163, 184, 0.86);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .article-list {
    display: grid;
    gap: 12px;
  }

  .article-row {
    display: grid;
    gap: 8px;
    padding: 14px 16px;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.62);
    border: 1px solid rgba(148, 163, 184, 0.14);
  }

  .article-row header {
    display: flex;
    align-items: center;
    gap: 10px;
    justify-content: space-between;
  }

  .article-row h4 {
    margin: 0;
    font-size: 17px;
    line-height: 1.35;
  }

  .rank {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(103, 232, 249, 0.25), rgba(167, 139, 250, 0.25));
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: white;
    font-size: 13px;
    font-weight: 700;
  }

  .article-row p {
    color: rgba(226, 232, 240, 0.8);
    line-height: 1.6;
    margin: 0;
  }

  .footer {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    padding: 20px 24px;
    border-radius: 22px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(10, 16, 30, 0.72);
    color: rgba(226, 232, 240, 0.74);
    font-size: 14px;
  }

  .footer strong {
    color: #fff;
  }
`

function renderArticleRow(article: CardArticlePayload) {
  return (
    <article className="article-row" key={article.article_id}>
      <header>
        <span className="rank">{article.rank}</span>
        <h4>{article.title}</h4>
      </header>
      <p>{article.rendered_summary}</p>
    </article>
  )
}

function DailyTemplate({
  payload,
  payloadMode,
}: {
  payload: CardRenderPayload
  payloadMode: "request" | "demo"
}) {
  const featured = payload.featured_articles[0] ?? payload.sections[0]?.articles[0]
  const sideArticles = payload.featured_articles.slice(1, 3)

  return (
    <div
      className="card-shell"
      data-card-root
      data-layout-hint={payload.layout_hint}
      data-payload-mode={payloadMode}
      data-schema-version={payload.schema_version}
    >
      <style>{styles}</style>
      <div className="frame">
        <header className="masthead">
          <p className="eyebrow">AI DAILY / Card Renderer</p>
          <div className="title-row">
            <div>
              <h1 className="headline">{payload.issue.title}</h1>
              <p className="lede">
                {payload.issue.report_date} · Issue #{payload.issue.issue_number} ·{" "}
                {payload.issue.article_count} 篇精选。该模板只负责呈现，不关心抓取、分类或持久化。
              </p>
            </div>
            <div className="badge-row">
              <span className="badge">
                <strong>layout</strong> {payload.layout_hint}
              </span>
              <span className="badge">
                <strong>schema</strong> {payload.schema_version}
              </span>
            </div>
          </div>
          <div className="meta-row">
            <span className="badge">
              <strong>source</strong> {payload.issue.github_url}
            </span>
            <span className="badge">
              <strong>backup</strong> {payload.issue.backup_filename}
            </span>
            <span className="badge">
              <strong>status</strong> {payload.issue.status}
            </span>
          </div>
        </header>

        <section className="hero-grid">
          <article className="spotlight">
            <div className="spotlight-top">
              <p className="spotlight-label">Featured Article</p>
              <span className="badge">
                <strong>count</strong> {payload.featured_articles.length}
              </span>
            </div>
            {featured ? (
              <>
                <h2 className="spotlight-title">{featured.title}</h2>
                <p className="spotlight-summary">{featured.rendered_summary}</p>
                <div className="meta-row">
                  <span className="badge">
                    <strong>article</strong> #{featured.article_id}
                  </span>
                  <span className="badge">
                    <strong>score</strong> {featured.article_score.toFixed(1)}
                  </span>
                  <span className="badge">
                    <strong>rank</strong> {featured.rank}
                  </span>
                </div>
              </>
            ) : (
              <p className="spotlight-summary">暂无精选内容。</p>
            )}
          </article>

          <aside className="stack">
            {sideArticles.map((article) => (
              <article className="stack-card" key={article.article_id}>
                <h3>{article.title}</h3>
                <p>{article.rendered_summary}</p>
              </article>
            ))}
          </aside>
        </section>

        <section className="section-grid">
          {payload.sections.map((section) => (
            <article className="section-card" key={section.name}>
              <div className="section-head">
                <h3>{section.name}</h3>
                <small>{section.articles.length} items</small>
              </div>
              <div className="article-list">{section.articles.map(renderArticleRow)}</div>
            </article>
          ))}
        </section>

        <footer className="footer">
          <span>
            视觉模板服务 · <strong>card-renderer</strong>
          </span>
          <span>{payload.issue.github_url}</span>
        </footer>
      </div>
    </div>
  )
}

function pickFirstString(value: SearchParamValue): string | null {
  if (typeof value === "string") {
    return value
  }
  if (Array.isArray(value) && typeof value[0] === "string") {
    return value[0]
  }
  return null
}

function resolvePayload(searchParams: SearchParams): {
  payload: CardRenderPayload
  mode: "request" | "demo"
} {
  const raw = pickFirstString(searchParams.payload)
  if (!raw) {
    return {
      payload: createDemoCardRenderPayload(),
      mode: "demo",
    }
  }

  const payloadCandidates = [raw]
  try {
    const decoded = decodeURIComponent(raw)
    if (decoded !== raw) {
      payloadCandidates.unshift(decoded)
    }
  } catch {
    // Keep raw candidate when value is already decoded or malformed.
  }

  for (const candidate of payloadCandidates) {
    try {
      return {
        payload: normalizeCardRenderPayload(JSON.parse(candidate)),
        mode: "request",
      }
    } catch {
      // Try next candidate.
    }
  }

  return {
    payload: createDemoCardRenderPayload(),
    mode: "demo",
  }
}

export default async function DailyTemplatePage({
  searchParams,
}: {
  searchParams?: Promise<SearchParams>
}) {
  const resolved = searchParams ? await searchParams : {}
  const { payload, mode } = resolvePayload(resolved)
  return <DailyTemplate payload={payload} payloadMode={mode} />
}
