# card-renderer

The card renderer is a presentation layer, not a data source.

## Scaffold

The minimal Next.js service lives under:

- `services/card-renderer/package.json`
- `services/card-renderer/Dockerfile`
- `services/card-renderer/src/app/api/render/route.ts`
- `services/card-renderer/src/app/templates/daily/page.tsx`
- `services/card-renderer/src/lib/playwright.ts`

The service is intentionally single-purpose:

- one HTTP API: `POST /api/render`
- one visual template: `DailyTemplate`
- one rendering path: template route -> Playwright -> PNG

## Local setup

```bash
cd services/card-renderer
npm install
npx playwright install chromium
```

## Input

Use the export payload from SQLite:

```bash
PYTHONPATH=src python -m ai_daily.cli export-card-payload --issue-number 1 --output services/card-renderer/output/issue_1.json
```

The payload contains:

- issue metadata
- ordered sections
- ranked articles per section
- featured articles for hero placement

## Expected output

- `PNG` for a single card
- `PNG` for a long poster
- optional preview artifacts during local development

## Recommended implementation shape

- Next.js template system for layout composition
- Playwright for headless browser capture
- local output directory under `services/card-renderer/output/`
- single-container deployment with isolated browser lifecycle

The output directory is ignored by git so generated previews do not pollute the
repository history.

## Local smoke test

```bash
cd services/card-renderer
npm run dev -- --port 3300
curl -sS -o output/smoke.png -w "%{http_code}\n" \
  -X POST http://127.0.0.1:3300/api/render \
  -H "Content-Type: application/json" \
  --data-binary @smoke-request.json
```
