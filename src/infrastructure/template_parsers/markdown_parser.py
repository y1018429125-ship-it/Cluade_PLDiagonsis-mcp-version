"""Markdown 模板解析器"""

import re
from pathlib import Path

from .base import TemplateParser, ParsedTemplate


class MarkdownTemplateParser(TemplateParser):
    """解析 .md 模板文件"""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".md"

    def parse(self, file_path: Path) -> ParsedTemplate:
        content = file_path.read_text(encoding="utf-8")
        chapters = self._extract_chapters(content)

        return ParsedTemplate(
            name=file_path.stem,
            source_file=str(file_path),
            source_format="md",
            content=content,
            chapters=chapters,
        )

    def _extract_chapters(self, content: str) -> list[dict]:
        chapters = []
        for line in content.splitlines():
            match = re.match(r"^(#{2,3})\s+(.+)", line)
            if match:
                chapters.append({
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                })
        return chapters
