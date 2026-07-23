"""Tests for src/domain/report_engine.py — mocked LLM and EventBus."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.core.models import (
    ChapterConfig,
    ConfidenceLevel,
    DiagnosisResult,
    DiagnosisSummary,
    FaultContext,
    RenderMode,
    TemplateConfig,
    ToolOutput,
)
from src.domain.report_engine import ReportEngine


@pytest.fixture
def report_engine() -> ReportEngine:
    """Return a ReportEngine with mocked dependencies."""
    mock_llm = AsyncMock()
    mock_event_bus = AsyncMock()
    return ReportEngine(mock_llm, mock_event_bus)


@pytest.fixture
def sample_summary() -> DiagnosisSummary:
    """Return a DiagnosisSummary with one result."""
    return DiagnosisSummary(
        fault_context=FaultContext(line_id="L1", line_name="京西线"),
        results=[
            DiagnosisResult(
                fault_type="雷击",
                confidence=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                tool_name="LightningDiagnosisTool",
                details={"raw_text": "检测到雷击"},
            ),
        ],
    )


@pytest.fixture
def sample_tool_outputs() -> dict[str, ToolOutput]:
    """Return a dict of ToolOutput samples."""
    return {
        "LightningDiagnosisTool": ToolOutput(
            tool_name="LightningDiagnosisTool",
            raw_text="雷击结果",
            structured_data={"distance": 1.2, "intensity": "high"},
        ),
        "WindDiagnosisTool": ToolOutput(
            tool_name="WindDiagnosisTool",
            raw_text="大风结果",
            structured_data={"speed": 25.0},
        ),
    }


# ============================================================================
# _filter_relevant_outputs
# ============================================================================


def test_filter_relevant_outputs_uses_data_sources(report_engine: ReportEngine) -> None:
    """_filter_relevant_outputs() filters by chapter.data_sources."""
    chapter = ChapterConfig(
        chapter_type="evidence",
        title="证据",
        data_sources=["LightningDiagnosisTool"],
    )
    outputs = {
        "LightningDiagnosisTool": ToolOutput(tool_name="L"),
        "WindDiagnosisTool": ToolOutput(tool_name="W"),
    }
    summary = DiagnosisSummary(fault_context=FaultContext(line_id="L1", line_name="京西线"))

    result = report_engine._filter_relevant_outputs(chapter, outputs, summary)

    assert list(result.keys()) == ["LightningDiagnosisTool"]


def test_filter_relevant_outputs_returns_all_for_evidence(report_engine: ReportEngine) -> None:
    """_filter_relevant_outputs() returns all outputs for evidence chapter."""
    chapter = ChapterConfig(chapter_type="evidence", title="诊断证据")
    outputs = {"A": ToolOutput(tool_name="A"), "B": ToolOutput(tool_name="B")}
    summary = DiagnosisSummary(fault_context=FaultContext(line_id="L1", line_name="京西线"))

    result = report_engine._filter_relevant_outputs(chapter, outputs, summary)

    assert len(result) == 2


def test_filter_relevant_outputs_returns_all_for_other_types(report_engine: ReportEngine) -> None:
    """_filter_relevant_outputs() returns all outputs for non-evidence chapters."""
    chapter = ChapterConfig(chapter_type="conclusion", title="结论")
    outputs = {"A": ToolOutput(tool_name="A")}
    summary = DiagnosisSummary(fault_context=FaultContext(line_id="L1", line_name="京西线"))

    result = report_engine._filter_relevant_outputs(chapter, outputs, summary)

    assert len(result) == 1


# ============================================================================
# _render_table
# ============================================================================


@pytest.mark.asyncio
async def test_render_table_with_structured_data(report_engine: ReportEngine) -> None:
    """_render_table() renders markdown table from structured_data."""
    chapter = ChapterConfig(chapter_type="evidence", title="证据")
    outputs = {
        "ToolA": ToolOutput(
            tool_name="ToolA",
            structured_data={"field1": "value1"},
        ),
    }

    result = await report_engine._render_table(chapter, outputs)

    assert "## 证据" in result
    assert "| 字段 | 值 |" in result
    assert "| field1 | value1 |" in result


@pytest.mark.asyncio
async def test_render_table_falls_back_to_raw_text(report_engine: ReportEngine) -> None:
    """_render_table() falls back to raw_text when structured_data is absent."""
    chapter = ChapterConfig(chapter_type="evidence", title="证据")
    outputs = {
        "ToolA": ToolOutput(tool_name="ToolA", raw_text="plain result"),
    }

    result = await report_engine._render_table(chapter, outputs)

    assert "plain result" in result


# ============================================================================
# _render_text
# ============================================================================


@pytest.mark.asyncio
async def test_render_text_calls_llm_chat(report_engine: ReportEngine) -> None:
    """_render_text() calls llm.chat() with a prompt."""
    report_engine.llm.chat = AsyncMock(return_value="generated text")
    chapter = ChapterConfig(chapter_type="conclusion", title="结论")
    summary = DiagnosisSummary(fault_context=FaultContext(line_id="L1", line_name="京西线"))

    result = await report_engine._render_text(chapter, {}, summary)

    assert result == "generated text"
    report_engine.llm.chat.assert_awaited_once()


# ============================================================================
# _render_mixed
# ============================================================================


@pytest.mark.asyncio
async def test_render_mixed_combines_table_and_analysis(report_engine: ReportEngine) -> None:
    """_render_mixed() returns table part plus LLM analysis."""
    report_engine.llm.chat = AsyncMock(return_value="analysis text")
    chapter = ChapterConfig(chapter_type="evidence", title="证据", render_mode=RenderMode.MIXED)
    outputs = {
        "ToolA": ToolOutput(tool_name="ToolA", structured_data={"k": "v"}),
    }
    summary = DiagnosisSummary(fault_context=FaultContext(line_id="L1", line_name="京西线"))

    result = await report_engine._render_mixed(chapter, outputs, summary)

    assert "## 证据" in result
    assert "### 分析" in result
    assert "analysis text" in result


# ============================================================================
# _outputs_to_text
# ============================================================================


def test_outputs_to_text_formats_structured_and_raw(report_engine: ReportEngine) -> None:
    """_outputs_to_text() formats both structured_data and raw_text."""
    outputs = {
        "ToolA": ToolOutput(
            tool_name="ToolA",
            structured_data={"key": "val"},
            raw_text="raw",
        ),
    }

    result = report_engine._outputs_to_text(outputs)

    assert "【ToolA】" in result
    assert "key: val" in result
    assert "raw" in result


def test_outputs_to_text_handles_empty_outputs(report_engine: ReportEngine) -> None:
    """_outputs_to_text() returns empty string for empty outputs."""
    result = report_engine._outputs_to_text({})
    assert result == ""


# ============================================================================
# _assemble_report
# ============================================================================


def test_assemble_report_joins_chapters(report_engine: ReportEngine) -> None:
    """_assemble_report() assembles chapters into a single markdown document."""
    chapters = [
        {"title": "概述", "type": "overview", "content": "overview content"},
        {"title": "结论", "type": "conclusion", "content": "conclusion content"},
    ]

    result = report_engine._assemble_report(chapters)

    assert "# 输电线路故障诊断报告" in result
    assert "overview content" in result
    assert "conclusion content" in result


# ============================================================================
# generate
# ============================================================================


@pytest.mark.asyncio
async def test_generate_publishes_events_and_returns_report(
    report_engine: ReportEngine,
    sample_summary: DiagnosisSummary,
    sample_tool_outputs: dict[str, ToolOutput],
) -> None:
    """generate() publishes thinking/complete events and returns assembled report."""
    template = TemplateConfig(
        name="default",
        chapters=[
            ChapterConfig(chapter_type="overview", title="概述", render_mode=RenderMode.TEXT),
        ],
    )
    report_engine.llm.chat = AsyncMock(return_value="overview text")

    result = await report_engine.generate(sample_summary, template, sample_tool_outputs, "s1")

    assert isinstance(result, str)
    assert "overview text" in result
    assert report_engine.event_bus.publish.await_count == 2
