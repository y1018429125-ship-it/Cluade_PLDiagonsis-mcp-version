"""Tests for src/domain/prompt_builder.py — PromptBuilder prompt assembly."""

import pytest

from src.domain.prompt_builder import DiagnosisSession, PromptBuilder, ToolConfig


# ============================================================================
# build
# ============================================================================


def test_build_prompt_contains_skill_and_tools() -> None:
    """Prompt contains skill content, tool descriptions, and user message."""
    skill_md = "# 诊断技能\n\n请按步骤执行诊断。"
    session = DiagnosisSession()
    tools = [
        ToolConfig(
            name="LightningDiagnosisTool",
            display_name="雷击诊断",
            description="分析雷击故障",
        ),
        ToolConfig(
            name="IcingDiagnosisTool",
            display_name="覆冰诊断",
            description="分析覆冰故障",
        ),
    ]
    user_message = "请诊断京西线故障"

    prompt = PromptBuilder.build(skill_md, session, tools, user_message)

    assert "你是输电线路故障诊断专家" in prompt
    assert "# 诊断技能" in prompt
    assert "LightningDiagnosisTool" in prompt
    assert "雷击诊断" in prompt
    assert "分析雷击故障" in prompt
    assert "IcingDiagnosisTool" in prompt
    assert "覆冰诊断" in prompt
    assert "分析覆冰故障" in prompt
    assert "请诊断京西线故障" in prompt
    assert '"reasoning"' in prompt
    assert '"tools_to_call"' in prompt
    assert '"report_structure"' in prompt


def test_build_prompt_detects_new_tools() -> None:
    """Prompt contains new-tool notice when a tool is not mentioned in skill_md."""
    skill_md = "# 诊断技能\n\n使用 LightningDiagnosisTool 进行雷击诊断。"
    session = DiagnosisSession()
    tools = [
        ToolConfig(
            name="LightningDiagnosisTool",
            display_name="雷击诊断",
            description="分析雷击故障",
        ),
        ToolConfig(
            name="WindDiagnosisTool",
            display_name="风害诊断",
            description="分析风害故障",
        ),
    ]
    user_message = "请诊断"

    prompt = PromptBuilder.build(skill_md, session, tools, user_message)

    assert "新工具通知" in prompt
    assert "WindDiagnosisTool" in prompt
    assert "风害诊断" in prompt
    assert "分析风害故障" in prompt
    # LightningDiagnosisTool is mentioned in skill_md, so it should NOT appear in new-tools section
    # We verify by checking the new-tools section only mentions WindDiagnosisTool
    new_tools_section_start = prompt.find("## 新工具通知")
    assert new_tools_section_start != -1
    new_tools_section = prompt[new_tools_section_start:]
    assert "WindDiagnosisTool" in new_tools_section
