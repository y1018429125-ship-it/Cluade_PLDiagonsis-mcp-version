"""Tests for src/domain/diagnosis_planner.py."""

from unittest.mock import AsyncMock

import pytest

from src.domain.diagnosis_planner import DEFAULT_PLAN, DiagnosisPlanner
from src.infrastructure.llm_service import LLMService


@pytest.fixture
def planner() -> DiagnosisPlanner:
    """Return a DiagnosisPlanner with a mocked LLMService."""
    mock_llm = AsyncMock(spec=LLMService)
    return DiagnosisPlanner(llm_service=mock_llm)


@pytest.mark.asyncio
async def test_plan_parses_llm_json(planner: DiagnosisPlanner) -> None:
    """Mock LLM returning valid JSON, verify plan is parsed correctly."""
    valid_plan = {
        "reasoning": "Call SCADA and weather tools",
        "tools_to_call": ["scada_reader", "weather_tool"],
        "report_structure": ["概述", "详细分析", "结论"],
    }
    planner.llm.chat = AsyncMock(return_value='{"reasoning": "Call SCADA and weather tools", "tools_to_call": ["scada_reader", "weather_tool"], "report_structure": ["概述", "详细分析", "结论"]}')

    result = await planner.plan("220kV线路跳闸，请诊断")

    assert result["reasoning"] == "Call SCADA and weather tools"
    assert result["tools_to_call"] == ["scada_reader", "weather_tool"]
    assert result["report_structure"] == ["概述", "详细分析", "结论"]

    # Verify the LLM was called with correct messages
    call_args = planner.llm.chat.call_args
    messages = call_args[0][0]
    assert messages[0]["role"] == "system"
    assert "诊断计划专家" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "220kV线路跳闸，请诊断"


@pytest.mark.asyncio
async def test_plan_fallback_on_invalid_json(planner: DiagnosisPlanner) -> None:
    """Mock LLM returning invalid text, verify fallback plan is returned."""
    planner.llm.chat = AsyncMock(return_value="这不是有效的 JSON 响应")

    result = await planner.plan("线路故障")

    assert result == DEFAULT_PLAN
    assert result["tools_to_call"] == []
    assert result["report_structure"] == ["概述", "故障分析", "诊断证据", "诊断结论", "处理建议"]
