# AI 早报 MVP 开发规划 V2.1

## 1. 项目目标

目标不是一次性复刻完整的“图文视频全自动早报帝国”，而是先做出一个可稳定日更的 `文字版早报 MVP`，并且为后续卡片、视频、垂直专报预留清晰扩展位。

MVP 交付物：

- 每天自动采集一批候选新闻
- 自动去重、分类、打分，生成候选池
- 自动生成一份“待审核日报草稿”
- 人工小改后，一键发布为正式日报
- 自动同步 `README`、`RSS`、`静态站点`、`Markdown 备份`

MVP 不包含：

- 自动抓取 `X/Discord` 全量内容
- 全自动卡片图与视频生产
- 复杂 CMS、多人权限系统、移动端 App

## 2. MVP 核心原则

- `Issue 是发布真源`：正式发布的日报以 GitHub Issue 为唯一发布源
- `SQLite 是加工层`：采集、去重、打分、缓存放在本地 SQLite
- `Python 是主引擎`：MVP 先统一用 Python 完成采集、编排、发布、站点生成
- `静态站点优先`：优先保证低成本部署、低维护成本和可回滚
- `人机协作`：AI 负责草稿生成和摘要，人负责最后审稿和发布

## 3. 第一版 MVP 技术选型

### 3.1 主技术栈

- `Python 3.12`
  说明：这是我的建议值，不是来自官方硬性要求。相较 `3.13`，它在第三方库兼容性上通常更稳，适合作为 MVP 默认版本。
- `Typer`
  用于做命令行入口，比如 `fetch`、`score`、`draft`、`publish`
- `SQLite`
  用于存候选新闻、去重指纹、抓取日志、发布状态
- `Pydantic`
  用于统一数据结构和配置校验
- `httpx + feedparser + beautifulsoup4 + trafilatura`
  用于 RSS/网页正文抓取和清洗
- `Jinja2 + Markdown + Feedgen`
  用于生成 Markdown、HTML、RSS
- `GitHub REST API / PyGithub`
  用于创建和更新 Issue、读取已发布日报
- `GitHub Actions + GitHub Pages`
  用于定时运行和静态站点部署

### 3.2 为什么 MVP 不先上 Next.js

- 当前最核心的不是前端互动，而是“采集到成刊”的稳定性
- Python 单栈更容易做抓取、清洗、去重、定时任务和文本编排
- 卡片服务后续可以单独作为 `services/card-renderer` 增量接入

### 3.3 后续扩展技术

- `Playwright`
  用于后续卡片图和海报截图。Playwright 官方支持直接截图页面或元素，适合做稳定导出。[官方文档](https://playwright.dev/python/docs/screenshots)
- `Next.js`
  用于第二阶段卡片渲染服务，不建议作为 MVP 的主架构
- `FFmpeg + TTS API`
  用于第三阶段视频化

### 3.4 GitHub 侧设计依据

- GitHub 支持通过 `/.github/ISSUE_TEMPLATE` 下的 YAML issue forms 来约束结构化输入，适合做日报发布模板。[GitHub Docs](https://docs.github.com/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- GitHub Pages 官方推荐通过 GitHub Actions 自定义工作流部署静态站点，适合本项目这种自定义构建链路。[GitHub Docs](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- GitHub Pages 官方提供 `configure-pages`、`upload-pages-artifact`、`deploy-pages` 这条标准部署路径，和 imjuya 的做法一致。[GitHub Docs](https://docs.github.com/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

### 3.5 LLM 稳定性策略

LLM 在 MVP 中只承担 `摘要` 和 `辅助分类`，不承担最终排序逻辑。

- `score.py` 保持为规则打分
  依据来源权重、时效性、关键词等透明规则计算，避免排序黑盒化
- `llm/client.py` 必须实现指数退避重试
  针对 `429` 和 `5xx` 至少进行 `3` 次带随机抖动的重试
- `llm_cache` 表必须作为缓存层
  通过 `task_type + model + prompt_hash + input_hash` 命中缓存，减少重复调用和成本
- `classify.py` 和 `summarizer.py` 必须具备降级能力
  LLM 超时或连续失败时自动回退到规则引擎，并将结果标记为 `degraded`
- 单条新闻的 LLM 失败不能拖垮整批流水线
  流水线应允许生成“降级版日报草稿”

## 4. 仓库目录设计

推荐先用单仓库，把 MVP 的主链打通，后续再按服务拆分。

```text
AI早报/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docs/
│   ├── AI早报MVP开发规划.md
│   ├── 信源清单.md
│   ├── Prompt策略.md
│   └── 发布流程SOP.md
├── config/
│   ├── settings.toml
│   ├── sources.yaml
│   ├── categories.yaml
│   └── prompts/
│       ├── summarize.txt
│       ├── classify.txt
│       └── draft_issue.txt
├── data/
│   ├── raw/
│   ├── staging/
│   ├── published/
│   ├── cache/
│   └── .gitkeep
├── site/
│   ├── templates/
│   ├── static/
│   └── generated/
├── scripts/
│   ├── bootstrap.sh
│   ├── run_daily.sh
│   └── export_issue_backup.sh
├── src/
│   └── ai_daily/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models/
│       │   ├── article.py
│       │   ├── issue.py
│       │   └── source.py
│       ├── storage/
│       │   ├── db.py
│       │   ├── article_repo.py
│       │   ├── issue_repo.py
│       │   ├── issue_article_repo.py
│       │   ├── llm_cache_repo.py
│       │   └── migrations.py
│       ├── fetchers/
│       │   ├── base.py
│       │   ├── adapter.py
│       │   ├── rss.py
│       │   ├── github.py
│       │   ├── arxiv.py
│       │   └── web.py
│       ├── pipeline/
│       │   ├── ingest.py
│       │   ├── dedupe.py
│       │   ├── score.py
│       │   ├── classify.py
│       │   ├── draft.py
│       │   └── publish.py
│       ├── llm/
│       │   ├── client.py
│       │   ├── summarizer.py
│       │   └── editor.py
│       ├── render/
│       │   ├── readme.py
│       │   ├── rss.py
│       │   ├── site.py
│       │   ├── backup.py
│       │   └── markdown.py
│       └── utils/
│           ├── dates.py
│           ├── hashes.py
│           ├── markdown.py
│           └── logging.py
├── tests/
│   ├── test_fetchers.py
│   ├── test_dedupe.py
│   ├── test_score.py
│   ├── test_publish.py
│   └── fixtures/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── daily_report.yml
│   │   └── source_feedback.yml
│   └── workflows/
│       ├── fetch_candidates.yml
│       ├── generate_draft.yml
│       ├── publish_site.yml
│       └── smoke_test.yml
└── BACKUP/
    └── .gitkeep
```

## 5. 模块职责

### 5.1 `fetchers/`

负责把不同来源的内容抓成统一结构。

架构上引入 `SourceAdapter` 适配器接口：

- `fetchers/rss.py`
  只处理标准 RSS
- `fetchers/adapter.py`
  负责把未来的非标准来源转换为统一输入
- RSSHub 不作为 Sprint 1 的强依赖
  但要为 `Sprint 2.5` 的接入预留扩展点

输入：

- RSS
- GitHub Releases
- GitHub Commits
- arXiv
- 官方博客网页

输出统一字段：

- `source_id`
- `source_type`
- `title`
- `url`
- `published_at`
- `author`
- `raw_text`
- `raw_html`
- `tags`

### 5.2 `pipeline/`

负责从“候选新闻”加工成“日报草稿”。

- `ingest.py`
  抓取并写入 SQLite
- `dedupe.py`
  根据 URL、标题、正文 hash 去重
- `score.py`
  根据信源权重、发布时间、关键词、互动热度打分
- `classify.py`
  按分类规则或 LLM 分类到栏目
- `draft.py`
  生成日报草稿 Markdown
- `publish.py`
  将审核后的日报发布到 GitHub Issue，并触发后续构建

### 5.3 `render/`

负责把已发布日报渲染成对外产物。

- `readme.py`
  更新首页最近日报列表
- `rss.py`
  更新 `rss.xml`
- `site.py`
  生成静态网页
- `backup.py`
  把 Issue 正文落盘到 `BACKUP/`
- `markdown.py`
  负责在正文中插入隐藏 HTML 注释，便于 `rebuild` 和人工排障

说明：

- `issue_articles` 表是“日报使用了哪些文章”的唯一结构化真源
- HTML 注释只是辅助溯源层，不替代数据库映射

### 5.4 `llm/`

负责与大模型交互，并保证自动化流水线稳定。

- `client.py`
  统一封装重试、缓存、超时、降级和错误分类
- `summarizer.py`
  生成摘要，失败时回退到规则摘要
- `editor.py`
  做轻量润色或结构调整，不允许成为发布链路的硬阻塞

## 6. 数据模型设计

### 6.1 `articles` 候选新闻表

建议字段：

- `id`
- `source_name`
- `source_type`
- `title`
- `url`
- `canonical_url`
- `published_at`
- `fetched_at`
- `raw_text`
- `summary`
- `category`
- `score`
- `dedupe_key`
- `metadata_snapshot`
  存抓取时的原始元数据快照，例如 star 数、作者、标签、原始发布时间
- `status`
  值建议：`new` / `filtered` / `selected` / `published` / `degraded`

### 6.2 `issues` 日报发布表

- `id`
- `issue_number`
- `report_date`
- `title`
- `status`
  值建议：`draft` / `published`
- `markdown_path`
- `github_url`
- `published_at`

### 6.3 `sources` 信源表

- `id`
- `name`
- `type`
- `url`
- `enabled`
- `weight`
- `fetch_interval_minutes`
- `parser`

### 6.4 `issue_articles` 日报与条目关联表

该表是审计闭环的核心。

- `issue_id`
- `article_id`
- `section`
  所属栏目，如 `模型发布`、`3DGS / XR 专报`
- `rank`
  在当前日报中的排序位置
- `title_snapshot`
  发布时的标题快照
- `source_url_snapshot`
  发布时的来源链接快照
- `article_score_snapshot`
  发布时的分数快照
- `rendered_summary`
  发布时最终写进日报的摘要快照

### 6.5 `llm_cache` LLM 缓存表

不要把所有 LLM 返回值直接塞进 `articles` 表，应单独维护缓存表。

- `id`
- `task_type`
  值建议：`summary` / `classify` / `rewrite_title`
- `model`
- `prompt_hash`
- `input_hash`
- `response_json`
- `status`
  值建议：`success` / `degraded` / `failed`
- `error_message`
- `created_at`

### 6.6 推荐索引与约束

- `articles(dedupe_key)` 建唯一索引
- `articles(canonical_url)` 视清洗稳定性考虑唯一索引或普通索引
- `issue_articles(issue_id, article_id)` 建唯一索引
- `llm_cache(task_type, model, prompt_hash, input_hash)` 建唯一索引

## 7. 第一版信源范围

MVP 先接低维护、结构清晰、可稳定抓取的来源。

### 7.1 通用 AI 早报最小信源集

- 官方博客 RSS 或博客页
  例如 OpenAI、Anthropic、Google AI、Microsoft AI
- GitHub Releases
  例如重点开源项目
- arXiv 分类页
  如 `cs.AI`、`cs.CL`、`cs.CV`
- Hacker News / 其他可 RSS 化社区

### 7.2 3DGS / XR 专报最小信源集

- arXiv：`cs.CV`、`cs.GR`
- GitHub：`graphdeco-inria/gaussian-splatting`、`nerfstudio-project/gsplat`、`playcanvas/supersplat`
- 官方博客：Luma、Polycam、PlayCanvas、DJI Enterprise、Esri
- Reddit RSS：`r/GaussianSplatting`、`r/3DScanning`、`r/virtualreality`

MVP 暂不自动化接入：

- X 全量抓取
- Discord 聊天抓取
- 微信公众号全文抓取

说明：

- RSSHub 是重要扩展位，但不是 Sprint 1 的硬前置
- MVP 先优先消化标准 RSS、GitHub、arXiv 和稳定博客页

## 8. 日报栏目设计

MVP 建议固定栏目，降低生成波动：

- `模型发布`
- `开发工具`
- `产品更新`
- `论文/研究`
- `行业动态`
- `3DGS / XR 专报`

如果当天某栏目为空，可以省略，不强行凑数。

## 9. 开发任务清单

### Epic A：项目基础设施

- 建立 Python 项目骨架
- 配置 `pyproject.toml`、格式化、日志、环境变量
- 初始化 `src/`、`tests/`、`config/`、`data/`、`site/`
- 增加 `.env.example`
- 增加 `docs/信源清单.md`
- 明确 workflow 触发边界与命名规范

验收标准：

- 本地可运行 `python -m ai_daily.cli --help`
- 项目可以安装依赖并通过基础 smoke test

### Epic B：数据层与配置层

- 建立 SQLite 数据库初始化脚本
- 建立 `articles`、`issues`、`sources`、`issue_articles`、`llm_cache` 表
- 实现仓储层 CRUD
- 建立 `sources.yaml` 信源配置加载逻辑
- 建立分类和权重配置
- 建立索引和迁移脚本

验收标准：

- 可以通过 CLI 初始化数据库
- 可以从配置文件读取信源并写入数据库
- `issue_articles` 与 `llm_cache` 可正常写入和查询

### Epic C：采集器

- 抽象 `BaseFetcher` 与 `SourceAdapter`
- 实现 RSS 抓取器
- 实现 GitHub Releases 抓取器
- 实现 arXiv 抓取器
- 实现网页正文抓取器
- 统一清洗输出格式

验收标准：

- 单次抓取后，数据库里能看到候选新闻
- 同一篇新闻重复抓取不会无限新增
- 非标准信源后续可通过适配器接入，不需要重写主采集链路

### Epic D：去重、打分、分类

- 实现 URL 去重
- 实现标题 hash 去重
- 实现正文相似度去重
- 实现按来源权重和时效性打分
- 实现规则分类
- 接入 LLM 做摘要与辅助分类
- 在 `llm/client.py` 中实现重试、缓存、超时和降级

验收标准：

- 候选池能够稳定输出一个排序列表
- 同类重复新闻只保留一条主记录
- LLM 不可用时，仍能生成降级版候选池和草稿

### Epic E：日报草稿生成

- 设计草稿 Markdown 模板
- 从候选池选出 Top N 新闻
- 自动生成概览和分栏目内容
- 生成“待审核日报草稿”到本地文件
- 支持指定日期重跑

验收标准：

- 可通过命令生成某天日报草稿
- 草稿结构稳定，不会出现乱序和大段空白

### Epic F：Issue 发布链路

- 建立日报 Issue Form
- 实现“从本地草稿发布到 GitHub Issue”
- 实现“读取已发布 Issue 重新生成 README/RSS/BACKUP”
- 记录 issue number 与发布日期映射
- 建立 `issue_articles` 映射写入逻辑
- 为每条新闻注入隐藏 HTML 注释元数据

验收标准：

- 能发布一篇正式日报到 GitHub Issue
- 发布后可自动生成 `README`、`rss.xml`、`BACKUP/*.md`
- 可以从 Issue 内容和数据库双向反查来源条目

### Epic G：静态站点

- 设计最简站点模板：首页、单篇页、RSS 链接
- 生成静态 HTML
- 部署到 GitHub Pages
- 增加自定义样式和 favicon

验收标准：

- 首页能浏览最近日报
- 单篇页可打开
- RSS 可被订阅器识别

### Epic H：自动化工作流

- 定时抓取候选新闻
- 手动触发生成日报草稿
- 发布后自动部署 Pages
- 增加失败日志与重试
- 对 bot 提交、路径和事件来源做严格隔离

验收标准：

- GitHub Actions 能定时运行
- 失败时能定位是抓取、生成还是部署问题
- 不会因自动 commit 或 Issue 更新触发工作流死循环

### Epic H 附：Workflow 强制规则

- `generate_draft.yml`
  优先使用 `workflow_dispatch` 或 `issues:labeled` 触发，例如加上 `trigger-draft` 标签后执行
- `publish_site.yml`
  监听 `BACKUP/**`、`site/**`、`config/**`、`src/ai_daily/render/**`，并保留 `workflow_dispatch`
- 对由 `push` 触发的自动化链路增加 actor 过滤
  例如 `if: github.actor != 'github-actions[bot]'`
- 自动提交信息统一带 `[skip ci]`
- 对 `schedule`、`workflow_dispatch`、`issues:labeled` 分别定义不同入口，避免一个工作流兼顾过多职责

## 10. 建议迭代顺序

### Sprint 1：把基础盘子搭起来

- 完成 Epic A、B
- 把 CLI、配置、SQLite 跑通

目标：

- 项目能启动
- 数据表和配置可用
- `issue_articles` 和 `llm_cache` 模式已就位

### Sprint 2：把候选池跑起来

- 完成 Epic C、D

目标：

- 能每天自动采到一批候选新闻
- 能去重和排序
- LLM 调用失败时不会导致整批任务中断

### Sprint 3：把日报产出来

- 完成 Epic E、F

目标：

- 能生成草稿
- 能发布为正式日报
- 能从已发布 Issue 反查其来源条目

### Sprint 4：把站点和自动化补齐

- 完成 Epic G、H

目标：

- 全链路自动化
- README、RSS、站点全部更新

## 11. CLI 设计建议

```bash
python -m ai_daily.cli init-db
python -m ai_daily.cli fetch --source all
python -m ai_daily.cli dedupe
python -m ai_daily.cli score
python -m ai_daily.cli draft --date 2026-04-15
python -m ai_daily.cli publish --date 2026-04-15
python -m ai_daily.cli build-site
python -m ai_daily.cli rebuild --issue 12
python -m ai_daily.cli llm-cache-stats
```

## 12. MVP 验收标准

满足以下条件就可以认为 MVP 可上线：

- 每天定时抓取至少 `20-50` 条候选内容
- 经过去重和打分后，可稳定沉淀出 `8-15` 条日报条目
- 能生成一份结构稳定的日报草稿
- 能将草稿发布为 GitHub Issue
- 发布后能自动更新 `README`、`RSS`、`静态站点`
- 同一天日报支持重跑和修复
- 抓取失败、部署失败时有日志
- LLM 服务不可用时，系统仍能输出带 `degraded` 标记的草稿
- 已发布日报可以通过 `issue_articles` 与隐藏注释双重追溯

## 13. 第二阶段预留位

当 MVP 稳定后，再新增下面两个服务：

### `services/card-renderer`

- 技术栈：`Next.js + React + Playwright`
- 输入：日报条目 JSON
- 输出：单条卡片 PNG、封面图、长图海报

### `services/video-maker`

- 技术栈：`Python + FFmpeg + TTS API`
- 输入：日报 Markdown
- 输出：`audio.mp3`、`timeline.json`、`SRT`、`mp4`

第二阶段再处理这些问题：

- Docker 或虚拟机资源配额
- Apple Silicon 的 `h264_videotoolbox` / `hevc_videotoolbox`
- 本地大规模音视频任务对日常开发环境的资源隔离

## 14. 当前最推荐的开工顺序

如果现在就开始做，我建议按下面顺序推进：

1. 先搭项目骨架和数据库
2. 先接 `RSS + GitHub Releases + arXiv`
3. 先把“候选池 -> 草稿 Markdown”打通
4. 再接 GitHub Issue 发布
5. 最后再补 README/RSS/Pages

原因很简单：

- 采集和成稿是项目真正的核心壁垒
- 站点展示只是外壳
- 卡片和视频都应该建立在稳定文本链路之上

## 15. 一句结论

这项目最稳的做法不是“先搭一个像橘鸦的页面”，而是先做一条 `可持续日更的内容流水线`。只要这条主链稳定，卡片、视频、垂直专报都会变成顺延工作，而不是新的重构。
