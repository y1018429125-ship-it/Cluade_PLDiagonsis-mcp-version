"""Tests for DiagnoseCommand with LLM-orchestrated flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import (
    DiagnosisContext,
    DiagnosisSession,
    EventType,
    ExecutionContext,
    FaultContext,
    SessionStatus,
    ToolOutput,
)
from src.application.commands.diagnose import DiagnoseCommand


@pytest.fixture
def diagnose_command() -> DiagnoseCommand:
    """Return a DiagnoseCommand with all mocked dependencies."""
    mock_registry = MagicMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_event_bus = MagicMock()
    mock_skill_loader = MagicMock()
    mock_prompt_builder = MagicMock()
    mock_diagnosis_planner = AsyncMock()
    mock_tool_executor = AsyncMock()
    mock_report_composer = AsyncMock()

    mock_state_machine.can_execute.return_value = True
    mock_skill_loader.load.return_value = ("# skill", {})
    mock_prompt_builder.build.return_value = "prompt"
    mock_diagnosis_planner.plan.return_value = {
        "tools_to_call": [{"name": "ToolA"}],
        "report_structure": ["概述", "故障分析"],
    }
    mock_tool_executor.execute.return_value = {
        "ToolA": ToolOutput(tool_name="ToolA", raw_text="ok"),
    }
    mock_report_composer.compose.return_value = {"report": "# report", "summary": {"fault_type": "雷击", "confidence": 0.85, "primary_tool": "ToolA"}}

    return DiagnoseCommand(
        tool_registry=mock_registry,
        session_manager=mock_session_manager,
        state_machine=mock_state_machine,
        event_bus=mock_event_bus,
        skill_loader=mock_skill_loader,
        prompt_builder=mock_prompt_builder,
        diagnosis_planner=mock_diagnosis_planner,
        tool_executor=mock_tool_executor,
        report_composer=mock_report_composer,
    )


@pytest.mark.asyncio
async def test_diagnose_command_uses_new_flow(diagnose_command: DiagnoseCommand) -> None:
    """Verify DiagnoseCommand uses the new LLM-orchestrated flow."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="武汉线",
        status=SessionStatus.PENDING,
    )
    diagnosis_ctx = DiagnosisContext(
        session_id="s1",
        line_name="武汉线",
        fault_context=FaultContext(
            line_id="s1",
            line_name="武汉线",
            fault_time=None,
            additional_info={},
        ),
    )
    ctx = ExecutionContext(
        session=session,
        diagnosis_ctx=diagnosis_ctx,
        user_message="武汉线跳闸",
    )

    events = [e async for e in diagnose_command.execute(ctx)]

    # Verify new dependencies were called
    diagnose_command.skill_loader.load.assert_called_once()
    diagnose_command.prompt_builder.build.assert_called_once()
    diagnose_command.diagnosis_planner.plan.assert_called_once()
    diagnose_command.tool_executor.execute.assert_called_once()
    diagnose_command.report_composer.compose.assert_called_once()

    # Verify events were yielded (at least start + complete)
    assert events[0].event_type == EventType.START
    assert events[-1].event_type == EventType.COMPLETE
