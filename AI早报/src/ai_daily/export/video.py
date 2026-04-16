from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ai_daily.config import PROJECT_ROOT

SECTION_PATTERN = re.compile(r"^##\s+(?P<section>.+?)\s*$")
ARTICLE_PATTERN = re.compile(r"^###\s+\[(?P<title>.+?)\]\((?P<url>.+?)\)\s*$")
TITLE_PATTERN = re.compile(r"^#\s+(?P<title>.+?)\s*$")
SOURCE_PATTERN = re.compile(r"^>\s*发布源：(?P<github_url>.+?)\s*$")
REPORT_DATE_PATTERN = re.compile(r"^>\s*报告日期：(?P<report_date>\d{4}-\d{2}-\d{2})\s*$")
ISSUE_NUMBER_PATTERN = re.compile(r"^>\s*Issue 编号：#(?P<issue_number>\d+)\s*$")
ARTICLE_METADATA_PATTERN = re.compile(
    r"<!--\s*article_id:(?P<article_id>\d+)\s+source_url:(?P<source_url>\S+)\s+"
    r"dedupe_key:(?P<dedupe_key>\S+)\s*-->"
)


@dataclass(slots=True)
class MarkdownArticleBlock:
    article_id: int
    section: str
    rank: int
    title: str
    url: str
    rendered_summary: str
    source_url: str
    dedupe_key: str


@dataclass(slots=True)
class VideoSectionPlan:
    name: str
    articles: list[MarkdownArticleBlock] = field(default_factory=list)


@dataclass(slots=True)
class ParsedBackupIssue:
    issue_number: int
    report_date: str
    title: str
    github_url: str
    backup_path: str
    sections: list[VideoSectionPlan] = field(default_factory=list)

    @property
    def article_count(self) -> int:
        return sum(len(section.articles) for section in self.sections)


@dataclass(slots=True)
class TimelineSegment:
    index: int
    kind: str
    start_seconds: float
    duration_seconds: float
    text: str
    section: str = ""
    article_id: int | None = None
    article_title: str = ""
    article_url: str = ""
    source_url: str = ""
    dedupe_key: str = ""


@dataclass(slots=True)
class VideoPlan:
    issue_number: int
    report_date: str
    title: str
    github_url: str
    backup_path: str
    article_count: int
    section_count: int
    sections: list[VideoSectionPlan] = field(default_factory=list)
    timeline: list[TimelineSegment] = field(default_factory=list)
    narration_lines: list[str] = field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    schema_version: str = field(default="video-plan.v1", init=False)


@dataclass(slots=True)
class VideoArtifactPaths:
    timeline_path: Path
    subtitles_path: Path
    narration_path: Path


def default_backup_path(issue_number: int) -> Path:
    return PROJECT_ROOT / "BACKUP" / f"issue_{issue_number}.md"


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _estimate_duration(
    text: str,
    *,
    base: float,
    minimum: float,
    maximum: float,
    per_char: float,
) -> float:
    normalized = _normalize_text(text)
    duration = base + len(normalized) * per_char
    return round(max(minimum, min(maximum, duration)), 2)


def _format_timestamp(total_seconds: float) -> str:
    total_milliseconds = int(round(total_seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _flush_article(
    *,
    sections: OrderedDict[str, list[MarkdownArticleBlock]],
    current_section: str,
    article_title: str,
    article_url: str,
    summary_lines: list[str],
    metadata: dict[str, str],
    section_counters: dict[str, int],
) -> None:
    if not article_title:
        return

    raw_source_url = metadata.get("source_url", article_url)
    raw_dedupe_key = metadata.get("dedupe_key", "").strip()
    if not raw_dedupe_key:
        raw_dedupe_key = hashlib.sha256(
            f"{article_title}|{article_url}".encode()
        ).hexdigest()

    if "article_id" in metadata:
        article_id = int(metadata["article_id"])
    else:
        article_id = int(raw_dedupe_key[:12], 16)

    normalized_summary = _normalize_text(" ".join(summary_lines)) or "待补充摘要"
    section_name = current_section or "未分类"
    rank = section_counters.get(section_name, 0) + 1
    section_counters[section_name] = rank
    sections.setdefault(section_name, []).append(
        MarkdownArticleBlock(
            article_id=article_id,
            section=section_name,
            rank=rank,
            title=article_title,
            url=article_url,
            rendered_summary=normalized_summary,
            source_url=raw_source_url,
            dedupe_key=raw_dedupe_key,
        )
    )


def parse_backup_markdown(content: str, *, backup_path: Path | None = None) -> ParsedBackupIssue:
    issue_number: int | None = None
    report_date: str | None = None
    title: str | None = None
    github_url = ""
    current_section = "未分类"
    current_article_title = ""
    current_article_url = ""
    current_summary_lines: list[str] = []
    current_metadata: dict[str, str] = {}
    section_counters: dict[str, int] = {}
    sections: OrderedDict[str, list[MarkdownArticleBlock]] = OrderedDict()

    def flush_current_article() -> None:
        nonlocal current_article_title, current_article_url, current_summary_lines, current_metadata
        _flush_article(
            sections=sections,
            current_section=current_section,
            article_title=current_article_title,
            article_url=current_article_url,
            summary_lines=current_summary_lines,
            metadata=current_metadata,
            section_counters=section_counters,
        )
        current_article_title = ""
        current_article_url = ""
        current_summary_lines = []
        current_metadata = {}

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current_article_title:
                current_summary_lines.append("")
            continue

        if match := TITLE_PATTERN.match(line):
            title = match.group("title").strip()
            continue
        if match := SOURCE_PATTERN.match(line):
            github_url = match.group("github_url").strip()
            continue
        if match := REPORT_DATE_PATTERN.match(line):
            report_date = match.group("report_date").strip()
            continue
        if match := ISSUE_NUMBER_PATTERN.match(line):
            issue_number = int(match.group("issue_number"))
            continue

        if match := SECTION_PATTERN.match(line):
            if current_article_title:
                flush_current_article()
            current_section = match.group("section").strip() or "未分类"
            sections.setdefault(current_section, [])
            continue

        if match := ARTICLE_PATTERN.match(line):
            if current_article_title:
                flush_current_article()
            current_article_title = match.group("title").strip()
            current_article_url = match.group("url").strip()
            current_summary_lines = []
            current_metadata = {}
            continue

        if match := ARTICLE_METADATA_PATTERN.match(line):
            current_metadata = match.groupdict()
            if current_article_title:
                flush_current_article()
            continue

        if current_article_title:
            current_summary_lines.append(line.strip())

    if current_article_title:
        flush_current_article()

    if issue_number is None or report_date is None or title is None or not github_url:
        raise ValueError("Backup markdown is missing required issue metadata")

    return ParsedBackupIssue(
        issue_number=issue_number,
        report_date=report_date,
        title=title,
        github_url=github_url,
        backup_path=str(backup_path) if backup_path else "",
        sections=[
            VideoSectionPlan(name=section_name, articles=articles)
            for section_name, articles in sections.items()
        ],
    )


def build_video_plan(parsed: ParsedBackupIssue) -> VideoPlan:
    timeline: list[TimelineSegment] = []
    narration_lines: list[str] = []
    current_start = 0.0
    segment_index = 1
    sections: list[VideoSectionPlan] = []

    intro_text = (
        f"{parsed.title}。{parsed.report_date}。共 {parsed.article_count} 条精选内容。"
    )
    intro_duration = _estimate_duration(
        intro_text,
        base=3.0,
        minimum=4.0,
        maximum=7.0,
        per_char=0.03,
    )
    timeline.append(
        TimelineSegment(
            index=segment_index,
            kind="intro",
            start_seconds=current_start,
            duration_seconds=intro_duration,
            text=intro_text,
        )
    )
    narration_lines.append(intro_text)
    current_start += intro_duration
    segment_index += 1

    for section in parsed.sections:
        sections.append(VideoSectionPlan(name=section.name, articles=list(section.articles)))
        section_text = f"栏目：{section.name}。"
        section_duration = _estimate_duration(
            section_text,
            base=1.8,
            minimum=2.5,
            maximum=4.0,
            per_char=0.05,
        )
        timeline.append(
            TimelineSegment(
                index=segment_index,
                kind="section",
                start_seconds=current_start,
                duration_seconds=section_duration,
                text=section_text,
                section=section.name,
            )
        )
        narration_lines.append(section_text)
        current_start += section_duration
        segment_index += 1

        for article in section.articles:
            article_text = f"{article.title}。{article.rendered_summary}"
            article_duration = _estimate_duration(
                article_text,
                base=4.0,
                minimum=5.0,
                maximum=12.0,
                per_char=0.045,
            )
            timeline.append(
                TimelineSegment(
                    index=segment_index,
                    kind="article",
                    start_seconds=current_start,
                    duration_seconds=article_duration,
                    text=article_text,
                    section=article.section,
                    article_id=article.article_id,
                    article_title=article.title,
                    article_url=article.url,
                    source_url=article.source_url,
                    dedupe_key=article.dedupe_key,
                )
            )
            narration_lines.append(article_text)
            current_start += article_duration
            segment_index += 1

    closing_text = f"更多内容见 {parsed.github_url}。"
    closing_duration = _estimate_duration(
        closing_text,
        base=2.0,
        minimum=2.5,
        maximum=5.0,
        per_char=0.03,
    )
    timeline.append(
        TimelineSegment(
            index=segment_index,
            kind="closing",
            start_seconds=current_start,
            duration_seconds=closing_duration,
            text=closing_text,
        )
    )
    narration_lines.append(closing_text)
    current_start += closing_duration

    return VideoPlan(
        issue_number=parsed.issue_number,
        report_date=parsed.report_date,
        title=parsed.title,
        github_url=parsed.github_url,
        backup_path=parsed.backup_path,
        article_count=parsed.article_count,
        section_count=len(parsed.sections),
        sections=sections,
        timeline=timeline,
        narration_lines=narration_lines,
        estimated_duration_seconds=round(current_start, 2),
    )


def video_plan_to_dict(plan: VideoPlan) -> dict[str, object]:
    return asdict(plan)


def video_plan_to_json(plan: VideoPlan) -> str:
    return json.dumps(video_plan_to_dict(plan), ensure_ascii=False, indent=2)


def render_srt(plan: VideoPlan) -> str:
    cues: list[str] = []
    for segment in plan.timeline:
        start = _format_timestamp(segment.start_seconds)
        end = _format_timestamp(segment.start_seconds + segment.duration_seconds)
        cues.append(
            "\n".join(
                [
                    str(segment.index),
                    f"{start} --> {end}",
                    segment.text,
                ]
            )
        )
    return "\n\n".join(cues).strip() + ("\n" if cues else "")


def write_video_artifacts(plan: VideoPlan, output_dir: Path) -> VideoArtifactPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = output_dir / "timeline.json"
    subtitles_path = output_dir / "subtitles.srt"
    narration_path = output_dir / "narration.txt"

    timeline_path.write_text(video_plan_to_json(plan) + "\n", encoding="utf-8")
    subtitles_path.write_text(render_srt(plan), encoding="utf-8")
    narration_path.write_text("\n\n".join(plan.narration_lines).strip() + "\n", encoding="utf-8")

    return VideoArtifactPaths(
        timeline_path=timeline_path,
        subtitles_path=subtitles_path,
        narration_path=narration_path,
    )
