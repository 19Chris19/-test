# AI 早报

这是一个按 `V2.1` 规划落地中的 AI 早报项目骨架。

当前已完成：

- Python 项目结构
- Typer CLI 入口
- SQLite Schema 与迁移骨架
- 配置加载
- 信源与栏目示例配置
- LLM 缓存与降级接口占位

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=src python -m ai_daily.cli init-db
PYTHONPATH=src python -m ai_daily.cli seed-sources
PYTHONPATH=src python -m ai_daily.cli fetch --source-type arxiv --limit 10
PYTHONPATH=src python -m ai_daily.cli dedupe
PYTHONPATH=src python -m ai_daily.cli score --dry-run
PYTHONPATH=src python -m ai_daily.cli classify
PYTHONPATH=src python -m ai_daily.cli draft --date 2026-04-15
PYTHONPATH=src python -m ai_daily.cli publish --date 2026-04-15 --dry-run
PYTHONPATH=src python -m ai_daily.cli generate-assets
```

## 当前命令

```bash
PYTHONPATH=src python -m ai_daily.cli show-config
PYTHONPATH=src python -m ai_daily.cli init-db
PYTHONPATH=src python -m ai_daily.cli seed-sources
PYTHONPATH=src python -m ai_daily.cli list-sources
PYTHONPATH=src python -m ai_daily.cli fetch --source-type arxiv --limit 10
PYTHONPATH=src python -m ai_daily.cli dedupe
PYTHONPATH=src python -m ai_daily.cli score --dry-run
PYTHONPATH=src python -m ai_daily.cli classify
PYTHONPATH=src python -m ai_daily.cli draft --date 2026-04-15
PYTHONPATH=src python -m ai_daily.cli publish --date 2026-04-15
PYTHONPATH=src python -m ai_daily.cli rebuild --issue-number 1
PYTHONPATH=src python -m ai_daily.cli generate-assets
PYTHONPATH=src python -m ai_daily.cli db-status
PYTHONPATH=src python -m ai_daily.cli llm-cache-stats
```

## 最近发布

- [2026-04-16 · #1 AI 早报 2026-04-16](https://github.com/19Chris19/-test/issues/1)
  - 备份：[issue_1.md](BACKUP/issue_1.md)

## 入口

- 静态站点：[site/generated/index.html](site/generated/index.html)
- RSS：[site/generated/rss.xml](site/generated/rss.xml)
- 发布真源：GitHub Issue

## 许可

仓库代码遵循 MIT 许可；`BACKUP/` 下的内容遵循 CC BY-NC 4.0。

核心规划文档见：

- [docs/AI早报MVP开发规划.md](docs/AI早报MVP开发规划.md)
