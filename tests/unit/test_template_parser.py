"""Tests for src/infrastructure/template_parser.py — template parsing logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import TemplateParseError
from src.core.models import ChapterConfig, RenderMode, TemplateConfig
from src.infrastructure.template_parser import TemplateParser


@pytest.fixture
def parser() -> TemplateParser:
    """Return a fresh TemplateParser instance."""
    return TemplateParser()


# ============================================================================
# _detect_chapter_type
# ============================================================================


def test_detect_chapter_type_finds_overview(parser: TemplateParser) -> None:
    """_detect_chapter_type maps '概述' to overview."""
    assert parser._detect_chapter_type("概述") == "overview"


def test_detect_chapter_type_finds_fault_analysis(parser: TemplateParser) -> None:
    """_detect_chapter_type maps '故障原因分析' to fault_analysis."""
    assert parser._detect_chapter_type("故障原因分析") == "fault_analysis"


def test_detect_chapter_type_finds_evidence(parser: TemplateParser) -> None:
    """_detect_chapter_type maps '诊断证据' to evidence."""
    assert parser._detect_chapter_type("诊断证据") == "evidence"


def test_detect_chapter_type_finds_conclusion(parser: TemplateParser) -> None:
    """_detect_chapter_type maps '诊断结论' to conclusion."""
    assert parser._detect_chapter_type("诊断结论") == "conclusion"


def test_detect_chapter_type_finds_recommendation(parser: TemplateParser) -> None:
    """_detect_chapter_type maps '处理建议' to recommendation."""
    assert parser._detect_chapter_type("处理建议") == "recommendation"


def test_detect_chapter_type_returns_custom_when_unknown(parser: TemplateParser) -> None:
    """_detect_chapter_type returns a custom prefix for unrecognized titles."""
    result = parser._detect_chapter_type("未知章节")
    assert result.startswith("custom_")


# ============================================================================
# _default_chapters
# ============================================================================


def test_default_chapters_returns_five_entries(parser: TemplateParser) -> None:
    """_default_chapters() returns the five standard chapters."""
    chapters = parser._default_chapters()
    assert len(chapters) == 5
    assert chapters[0].chapter_type == "overview"
    assert chapters[-1].chapter_type == "recommendation"


# ============================================================================
# _extract_chapters — mocked Document
# ============================================================================


def test_extract_chapters_from_headings(parser: TemplateParser) -> None:
    """_extract_chapters() parses Heading-style paragraphs."""
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.style.name = "Heading 1"
    mock_para.text = "  概述  "
    mock_doc.paragraphs = [mock_para]

    chapters = parser._extract_chapters(mock_doc)
    assert len(chapters) == 1
    assert chapters[0].chapter_type == "overview"
    assert chapters[0].title == "概述"


def test_extract_chapters_skips_non_heading_paragraphs(parser: TemplateParser) -> None:
    """_extract_chapters() ignores paragraphs without heading styles."""
    mock_doc = MagicMock()
    mock_doc.paragraphs = [
        MagicMock(style=MagicMock(name="Normal"), text="正文"),
    ]
    chapters = parser._extract_chapters(mock_doc)
    assert len(chapters) == 5  # falls back to defaults


def test_extract_chapters_uses_defaults_when_empty(parser: TemplateParser) -> None:
    """_extract_chapters() returns defaults when no headings are found."""
    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    chapters = parser._extract_chapters(mock_doc)
    assert len(chapters) == 5


# ============================================================================
# parse — file handling
# ============================================================================


def test_parse_raises_when_file_missing(parser: TemplateParser, tmp_path: Path) -> None:
    """parse() raises TemplateParseError for non-existent files."""
    with pytest.raises(TemplateParseError) as exc_info:
        parser.parse(tmp_path / "missing.docx")
    assert "不存在" in str(exc_info.value)


@patch("src.infrastructure.template_parser.Document")
def test_parse_returns_template_config(mock_document, parser: TemplateParser, tmp_path: Path) -> None:
    """parse() returns a TemplateConfig with extracted chapters."""
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.style.name = "Heading 1"
    mock_para.text = "诊断结论"
    mock_doc.paragraphs = [mock_para]
    mock_document.return_value = mock_doc

    file_path = tmp_path / "test_template.docx"
    file_path.write_text("fake docx content")

    result = parser.parse(file_path)

    assert isinstance(result, TemplateConfig)
    assert result.name == "test_template"
    assert result.source_file == str(file_path)
    assert len(result.chapters) == 1
    assert result.chapters[0].chapter_type == "conclusion"
