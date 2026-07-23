import pytest
from pathlib import Path

from src.infrastructure.template_parsers import (
    MarkdownTemplateParser,
    DocxTemplateParser,
    PdfTemplateParser,
)


class TestMarkdownTemplateParser:
    def test_parse_markdown(self, tmp_path):
        parser = MarkdownTemplateParser()
        md_file = tmp_path / "test.md"
        md_file.write_text("""# 报告模板

## 概述
简要描述。

## 故障分析
分析原因。
""")
        result = parser.parse(md_file)
        assert result.name == "test"
        assert result.source_format == "md"
        assert len(result.chapters) == 2
        assert result.chapters[0]["title"] == "概述"

    def test_supports_markdown(self):
        parser = MarkdownTemplateParser()
        assert parser.supports(Path("test.md")) is True
        assert parser.supports(Path("test.docx")) is False

    def test_parse_empty_markdown(self, tmp_path):
        parser = MarkdownTemplateParser()
        md_file = tmp_path / "empty.md"
        md_file.write_text("# 报告模板\n\n无章节。\n")
        result = parser.parse(md_file)
        assert result.name == "empty"
        assert len(result.chapters) == 0


class TestDocxTemplateParser:
    def test_supports_docx(self):
        parser = DocxTemplateParser()
        assert parser.supports(Path("test.docx")) is True
        assert parser.supports(Path("test.md")) is False
