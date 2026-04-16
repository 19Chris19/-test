from __future__ import annotations

from ai_daily.config import AppSettings
from ai_daily.models.publication import PublishedIssue


def render_readme(
    settings: AppSettings,
    issues: list[PublishedIssue],
    *,
    site_path: str = "site/generated/index.html",
    rss_path: str = "site/generated/rss.xml",
) -> str:
    recent = sorted(
        issues,
        key=lambda issue: (
            issue.published_at or "",
            issue.issue_number,
        ),
        reverse=True,
    )

    lines = [
        f"# {settings.site_title}",
        "",
        "这是一个按 `V2.1` 规划落地中的 AI 早报项目骨架。",
        "",
        "当前已完成：",
        "",
        "- Python 项目结构",
        "- Typer CLI 入口",
        "- SQLite Schema 与迁移骨架",
        "- 配置加载",
        "- 信源与栏目示例配置",
        "- LLM 缓存与降级接口占位",
        "- 多模态导出适配层",
        "",
        "## 快速开始",
        "",
        "```bash",
        "python3 -m venv .venv",
        "source .venv/bin/activate",
        'pip install -e ".[dev]"',
        "PYTHONPATH=src python -m ai_daily.cli init-db",
        "PYTHONPATH=src python -m ai_daily.cli seed-sources",
        "PYTHONPATH=src python -m ai_daily.cli fetch --source-type arxiv --limit 10",
        "PYTHONPATH=src python -m ai_daily.cli dedupe",
        "PYTHONPATH=src python -m ai_daily.cli score --dry-run",
        "PYTHONPATH=src python -m ai_daily.cli classify",
        "PYTHONPATH=src python -m ai_daily.cli draft --date 2026-04-15",
        "PYTHONPATH=src python -m ai_daily.cli publish --date 2026-04-15 --dry-run",
        "PYTHONPATH=src python -m ai_daily.cli export-card-payload --issue-number 1",
        "PYTHONPATH=src python -m ai_daily.cli build-video-plan --issue-number 1",
        "PYTHONPATH=src python -m ai_daily.cli generate-assets",
        "```",
        "",
        "## 当前命令",
        "",
        "```bash",
        "PYTHONPATH=src python -m ai_daily.cli show-config",
        "PYTHONPATH=src python -m ai_daily.cli init-db",
        "PYTHONPATH=src python -m ai_daily.cli seed-sources",
        "PYTHONPATH=src python -m ai_daily.cli list-sources",
        "PYTHONPATH=src python -m ai_daily.cli fetch --source-type arxiv --limit 10",
        "PYTHONPATH=src python -m ai_daily.cli dedupe",
        "PYTHONPATH=src python -m ai_daily.cli score --dry-run",
        "PYTHONPATH=src python -m ai_daily.cli classify",
        "PYTHONPATH=src python -m ai_daily.cli draft --date 2026-04-15",
        "PYTHONPATH=src python -m ai_daily.cli publish --date 2026-04-15",
        "PYTHONPATH=src python -m ai_daily.cli export-card-payload --issue-number 1",
        "PYTHONPATH=src python -m ai_daily.cli build-video-plan --issue-number 1",
        "PYTHONPATH=src python -m ai_daily.cli rebuild --issue-number 1",
        "PYTHONPATH=src python -m ai_daily.cli generate-assets",
        "PYTHONPATH=src python -m ai_daily.cli db-status",
        "PYTHONPATH=src python -m ai_daily.cli llm-cache-stats",
        "```",
        "",
    ]

    if recent:
        lines.extend(["## 最近发布", ""])
        for issue in recent[:10]:
            lines.extend(
                [
                    (
                        f"- [{issue.report_date} · #{issue.issue_number} "
                        f"{issue.title}]({issue.github_url})"
                    ),
                    f"  - 备份：[{issue.backup_filename}](BACKUP/{issue.backup_filename})",
                ]
            )
    else:
        lines.extend(["## 最近发布", "", "- 目前还没有已发布的 Issue。"])

    lines.extend(
        [
            "",
            "## 入口",
            "",
            f"- 静态站点：[{site_path}]({site_path})",
            f"- RSS：[{rss_path}]({rss_path})",
            "- 发布真源：GitHub Issue",
            "",
            "## 许可",
            "",
            "仓库代码遵循 MIT 许可；`BACKUP/` 下的内容遵循 CC BY-NC 4.0。",
            "",
            "核心规划文档见：",
            "",
            "- [docs/AI早报MVP开发规划.md](docs/AI早报MVP开发规划.md)",
        ]
    )
    return "\n".join(lines).strip() + "\n"
