import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.application.commands.diagnose import DiagnoseCommand
from src.core.models import (
    DiagnosisSession,
    SessionStatus,
    ToolOutput,
    ExecutionContext,
    DiagnosisContext,
    Intent,
    IntentType,
    FaultContext,
    Event,
)


@pytest.fixture
def sample_session():
    session = DiagnosisSession(
        session_id="sess_test",
        line_name="武汉线",
        status=SessionStatus.MODIFYING,
    )
    session.tool_outputs_cache = {
        "LightningDiagnosisTool": ToolOutput(
            tool_name="LightningDiagnosisTool",
            raw_text="雷电数据",
            structured_data={"confidence": 0.85},
        ),
        "IcingDiagnosisTool": ToolOutput(
            tool_name="IcingDiagnosisTool",
            raw_text="覆冰数据",
            structured_data={"confidence": 0.30},
        ),
    }
    return session


@pytest.mark.asyncio
async def test_fresh_diagnosis_clears_cache():
    """全新诊断（PENDING状态）应清除缓存"""
    session = DiagnosisSession(
        session_id="sess_fresh",
        line_name="武汉线",
        status=SessionStatus.PENDING,
    )
    session.tool_outputs_cache = {"old_tool": "old_data"}
    session.active_skill_name = "comprehensive_diagnosis"

    # Mock dependencies
    cmd = DiagnoseCommand(
        tool_registry=MagicMock(),
        session_manager=MagicMock(),
        state_machine=MagicMock(),
        event_bus=MagicMock(),
        skill_loader=MagicMock(),
        prompt_builder=MagicMock(),
        diagnosis_planner=MagicMock(),
        tool_executor=MagicMock(),
        report_composer=MagicMock(),
    )
    cmd.state_machine.can_execute.return_value = True
    cmd.skill_loader.load.return_value = ("# skill", {"LightningDiagnosisTool": 1.0})
    cmd.tool_registry.list_tools.return_value = []
    cmd.prompt_builder.build.return_value = "prompt"

    # Mock diagnosis planner
    plan = {"tools_to_call": [], "report_structure": ["概述"]}

    async def fake_plan(*args, on_chunk=None, **kwargs):
        if on_chunk:
            on_chunk("")
        return plan

    cmd.diagnosis_planner.plan = fake_plan

    # Mock report composer
    cmd.report_composer.compose = AsyncMock(
        return_value={
            "report": "report",
            "summary": {
                "fault_type": "测试",
                "confidence": 0.5,
                "primary_tool": "test",
            },
        }
    )

    ctx = ExecutionContext(
        session=session,
        diagnosis_ctx=DiagnosisContext(
            session_id=session.session_id, line_name=session.line_name
        ),
        user_message="测试",
    )

    # Consume all events
    async for _ in cmd.execute(ctx):
        pass

    assert session.tool_outputs_cache == {}


@pytest.mark.asyncio
async def test_rediagnosis_reuses_cached_outputs(sample_session):
    """重新诊断应复用缓存中的工具输出"""
    sample_session.status = SessionStatus.MODIFYING
    sample_session.active_skill_name = "comprehensive_diagnosis"

    cmd = DiagnoseCommand(
        tool_registry=MagicMock(),
        session_manager=MagicMock(),
        state_machine=MagicMock(),
        event_bus=MagicMock(),
        skill_loader=MagicMock(),
        prompt_builder=MagicMock(),
        diagnosis_planner=MagicMock(),
        tool_executor=MagicMock(),
        report_composer=MagicMock(),
    )
    cmd.state_machine.can_execute.return_value = True
    cmd.skill_loader.load.return_value = ("# skill", {})
    cmd.tool_registry.list_tools.return_value = []
    cmd.prompt_builder.build.return_value = "prompt"

    plan = {
        "tools_to_call": [
            {"name": "LightningDiagnosisTool"},
            {"name": "IcingDiagnosisTool"},
        ],
        "report_structure": ["概述"],
    }

    async def fake_plan(*args, on_chunk=None, **kwargs):
        if on_chunk:
            on_chunk("")
        return plan

    cmd.diagnosis_planner.plan = fake_plan

    # tool_executor should NOT be called when all tools are cached
    cmd.tool_executor.execute = AsyncMock(return_value={})

    cmd.report_composer.compose = AsyncMock(
        return_value={
            "report": "report",
            "summary": {
                "fault_type": "测试",
                "confidence": 0.5,
                "primary_tool": "test",
            },
        }
    )

    ctx = ExecutionContext(
        session=sample_session,
        diagnosis_ctx=DiagnosisContext(
            session_id=sample_session.session_id, line_name=sample_session.line_name
        ),
        user_message="测试",
    )

    events = []
    async for event in cmd.execute(ctx):
        events.append(event)

    # tool_executor.execute should not be called since all tools are cached
    cmd.tool_executor.execute.assert_not_called()

    # Cache should still contain both tools
    assert "LightningDiagnosisTool" in sample_session.tool_outputs_cache
    assert "IcingDiagnosisTool" in sample_session.tool_outputs_cache
