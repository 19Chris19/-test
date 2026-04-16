from __future__ import annotations

import re


def strip_markdown_links(text: str) -> str:
    return re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

