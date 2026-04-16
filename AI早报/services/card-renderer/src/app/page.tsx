const endpointExample = `POST /api/render

{
  "payload": {
    "issue": { ... },
    "sections": [ ... ],
    "featured_articles": [ ... ],
    "layout_hint": "poster",
    "schema_version": "card-render.v1"
  },
  "viewport": { "width": 1200, "height": 1600, "deviceScaleFactor": 2 },
  "timeoutMs": 15000
}`

export default function HomePage() {
  return (
    <main className="service-page">
      <section className="service-hero">
        <p className="eyebrow">AI 早报 / card-renderer</p>
        <h1>单容器视觉模板服务</h1>
        <p className="lead">
          该服务只做一件事：消费 `CardRenderPayload`，通过 React 模板和 Playwright 输出 PNG。
        </p>
      </section>

      <section className="service-grid">
        <article className="service-card">
          <h2>控制面</h2>
          <p>唯一入口：<code>/api/render</code></p>
          <p>输入：标准化 JSON payload</p>
          <p>输出：PNG 或错误响应</p>
        </article>
        <article className="service-card">
          <h2>隔离边界</h2>
          <p>不连接 SQLite，不读取爬虫状态，不参与打分。</p>
          <p>页面预览仅用于模板校验。</p>
        </article>
      </section>

      <section className="service-code">
        <h2>请求示例</h2>
        <pre>{endpointExample}</pre>
      </section>
    </main>
  )
}
