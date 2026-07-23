"""Tests for src/domain/report_composer.py — single-shot LLM report generation."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.core.models import ChapterConfig, FaultContext, RenderMode, TemplateConfig, ToolOutput
from src.domain.report_composer import DEFAULT_CHAPTERS, ReportComposer


@pytest.fixture
def report_composer() -> ReportComposer:
    """Return a ReportComposer with a mocked LLMService."""
    mock_llm = AsyncMock()
    return ReportComposer(mock_llm)


@pytest.fixture
def sample_tool_outputs() -> dict[str, ToolOutput]:
    """Return a dict of ToolOutput samples."""
    return {
        "LightningDiagnosisTool": ToolOutput(
            tool_name="LightningDiagnosisTool",
            raw_text="检测到雷击，距离 1.2km",
            structured_data={"distance": 1.2, "intensity": "high"},
        ),
        "WindDiagnosisTool": ToolOutput(
            tool_name="WindDiagnosisTool",
            raw_text="大风天气，风速 25m/s",
            structured_data={"speed": 25.0},
        ),
    }


@pytest.fixture
def sample_template() -> TemplateConfig:
    """Return a TemplateConfig with custom chapters."""
    return TemplateConfig(
        name="custom",
        chapters=[
            ChapterConfig(
                chapter_type="overview",
                title="概述",
                required=True,
                render_mode=RenderMode.TEXT,
            ),
            ChapterConfig(
                chapter_type="conclusion",
                title="诊断结论",
                required=True,
                render_mode=RenderMode.TEXT,
            ),
        ],
    )


# ============================================================================
# compose
# ============================================================================


@pytest.mark.asyncio
async def test_compose_generates_report(
    report_composer: ReportComposer,
    sample_tool_outputs: dict[str, ToolOutput],
    sample_template: TemplateConfig,
) -> None:
    """compose() calls LLM with prompt containing tool data and returns formatted report."""
    report_composer.llm.chat = AsyncMock(
        return_value="## 概述\n概述内容\n\n## 诊断结论\n结论内容"
    )

    result = await report_composer.compose(
        tool_outputs=sample_tool_outputs,
        template=sample_template,
        session_id="sess-001",
    )

    # 验证输出包含章节和工具数据
    assert "## 概述" in result["report"]
    assert "## 诊断结论" in result["report"]
    assert "# 输电线路故障诊断报告" in result["report"]

    # 验证 LLM 被调用且 prompt 包含工具数据
    report_composer.llm.chat.assert_awaited_once()
    call_messages = report_composer.llm.chat.call_args.args[0]
    assert call_messages[0]["role"] == "system"
    assert "输电线路故障诊断报告撰写专家" in call_messages[0]["content"]
    assert call_messages[1]["role"] == "user"
    prompt = call_messages[1]["content"]
    assert "LightningDiagnosisTool" in prompt
    assert "WindDiagnosisTool" in prompt
    assert "检测到雷击" in prompt
    assert "25.0" in prompt
    assert "概述" in prompt
    assert "诊断结论" in prompt


@pytest.mark.asyncio
async def test_compose_without_template_uses_defaults(
    report_composer: ReportComposer,
    sample_tool_outputs: dict[str, ToolOutput],
) -> None:
    """compose() uses DEFAULT_CHAPTERS when template is None."""
    report_composer.llm.chat = AsyncMock(
        return_value="## 概述\n...\n## 故障分析\n..."
    )

    result = await report_composer.compose(
        tool_outputs=sample_tool_outputs,
        template=None,
        session_id="sess-002",
    )

    # 验证默认章节被使用
    report_composer.llm.chat.assert_awaited_once()
    call_messages = report_composer.llm.chat.call_args.args[0]
    prompt = call_messages[1]["content"]
    for chapter in DEFAULT_CHAPTERS:
        assert chapter in prompt

    # 验证返回结果
    assert "# 输电线路故障诊断报告" in result["report"]


class TestReportComposer:
    @pytest.fixture
    def composer(self):
        mock_llm = AsyncMock()
        return ReportComposer(mock_llm)

    @pytest.mark.asyncio
    async def test_compose_without_weights(self, composer):
        """ReportComposer 不再计算加权结果，summary 中不含 weighted_scores"""
        tool_outputs = {
            "ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.8, "fault_type": "雷击"}),
        }
        composer.llm.chat.return_value = "# 诊断报告\n\n测试内容。"

        result = await composer.compose(
            tool_outputs, None, "s1",
            fault_context=FaultContext(line_id="s1", line_name="京西线"),
        )

        # summary 中不应包含加权计算结果
        assert "weighted_scores" not in result["summary"]
        assert result["summary"]["fault_type"] == "雷击"
        assert result["summary"]["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_compose_loads_full_skill_content(self, composer, tmp_path):
        """compose() loads the complete skill markdown, not just a section."""
        from src.domain.skill_loader import SkillLoader

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_loader = SkillLoader(str(skills_dir))
        skill_content = """---
name: test_skill
description: test skill
---

# 诊断策略

## 核心算法
加权置信度 = confidence × weight

## 工具调用策略
| Tool | Condition |
|------|-----------|
| LightningDiagnosisTool | SKIP |

## 报告撰写规则
- Remove chapter 3 entirely
- Follow template structure strictly
"""
        skill_loader.save("test_skill", skill_content)

        composer.skill_loader = skill_loader
        tool_outputs = {
            "ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.8}),
        }
        composer.llm.chat.return_value = "# Report\n\nContent."

        await composer.compose(
            tool_outputs, None, "s1",
            active_skill_name="test_skill",
        )

        prompt = composer.llm.chat.call_args.args[0][1]["content"]
        assert "诊断技能指南（必须遵循）" in prompt
        assert "LightningDiagnosisTool | SKIP" in prompt
        assert "Remove chapter 3 entirely" in prompt
        assert "核心算法" in prompt
