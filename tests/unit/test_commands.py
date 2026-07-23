"""Tests for src/application/commands/*.py — Command classes with mocked dependencies."""

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions import InvalidStateError, ToolNotFoundError, WeightValidationError
from src.core.models import (
    ConfidenceLevel,
    DiagnosisContext,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisSummary,
    EventType,
    ExecutionContext,
    FaultContext,
    Intent,
    IntentType,
    SessionStatus,
    ToolOutput,
    UserAction,
)
from src.application.commands.adjust_weight import AdjustWeightCommand, WEIGHT_MIN, WEIGHT_MAX
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.include_tool import IncludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.save_skill import SaveSkillCommand


# ============================================================================
# Helpers
# ============================================================================


def _make_context(
    session: DiagnosisSession,
    message: str = "test message",
    intent: Intent | None = None,
) -> ExecutionContext:
    """Build an ExecutionContext for command tests."""
    diagnosis_ctx = DiagnosisContext(
        session_id=session.session_id,
        line_name=session.line_name,
        weights=session.active_weights.copy(),
        excluded_tools=session.excluded_tools.copy(),
        rechecked_tools=session.rechecked_tools.copy(),
    )
    return ExecutionContext(
        session=session,
        diagnosis_ctx=diagnosis_ctx,
        user_message=message,
        intent=intent,
    )


# ============================================================================
# AdjustWeightCommand
# ============================================================================


@pytest.fixture
def adjust_command() -> AdjustWeightCommand:
    """Return an AdjustWeightCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return AdjustWeightCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_adjust_weight_success(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in adjust_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    adjust_command.session_manager.update_weights.assert_called_once_with("s1", {"ToolA": 1.5})
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "adjust_weight"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"
    assert session.action_log[0].parameters["weight"] == 1.5


@pytest.mark.asyncio
async def test_adjust_weight_invalid_missing_tool_name(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_missing_weight(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when weight is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "weight" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_weight_value(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError for non-numeric weight."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "abc"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "无效" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_out_of_range(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises WeightValidationError when weight is out of range."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "5.0"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(WeightValidationError) as exc_info:
        [e async for e in adjust_command.execute(ctx)]

    assert "超出范围" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adjust_weight_invalid_state(adjust_command: AdjustWeightCommand) -> None:
    """adjust_weight raises InvalidStateError when state machine rejects."""
    adjust_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
        parameters={"tool_name": "ToolA", "weight": "1.5"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in adjust_command.execute(ctx)]


# ============================================================================
# ExcludeToolCommand
# ============================================================================


@pytest.fixture
def exclude_command() -> ExcludeToolCommand:
    """Return an ExcludeToolCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return ExcludeToolCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_exclude_tool_success(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in exclude_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    exclude_command.session_manager.exclude_tools.assert_called_once_with("s1", ["ToolA"])
    # When already in MODIFYING, no transition is triggered
    exclude_command.session_manager.transition.assert_not_called()
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "exclude"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"


@pytest.mark.asyncio
async def test_exclude_tool_missing_name(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in exclude_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_exclude_tool_invalid_state(exclude_command: ExcludeToolCommand) -> None:
    """exclude_tool raises InvalidStateError when state machine rejects."""
    exclude_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.EXCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in exclude_command.execute(ctx)]




# ============================================================================
# IncludeToolCommand
# ============================================================================


@pytest.fixture
def include_command() -> IncludeToolCommand:
    """Return an IncludeToolCommand with mocked dependencies."""
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return IncludeToolCommand(mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_include_tool_success(include_command: IncludeToolCommand) -> None:
    """include_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    session.excluded_tools = ["ToolA"]
    intent = Intent(
        intent_type=IntentType.INCLUDE_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in include_command.execute(ctx)]

    assert len(events) == 2
    assert events[0].event_type == EventType.THINKING
    assert events[1].event_type == EventType.COMPLETE
    include_command.session_manager.include_tools.assert_called_once_with("s1", ["ToolA"])
    assert len(session.action_log) == 1
    assert session.action_log[0].action_type == "include"
    assert session.action_log[0].parameters["tool_name"] == "ToolA"
# ============================================================================
# SaveSkillCommand
# ============================================================================


@pytest.fixture
def save_strategy_command(tmp_path: Path) -> SaveSkillCommand:
    """Return a SaveSkillCommand with mocked dependencies."""
    mock_llm = AsyncMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_skill_loader = MagicMock()
    mock_state_machine.can_execute.return_value = True
    # Create base skill file for the command to read
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    base_skill = skills_dir / "comprehensive_diagnosis.md"
    base_skill.write_text(
        "---\n"
        "name: comprehensive_diagnosis\n"
        "description: base skill\n"
        "---\n\n"
        "# 输电线路综合诊断\n\n"
        "## 核心算法：加权置信度\n\n"
        "加权置信度 = tool_confidence × tool_weight\n\n"
        "## 工具权重配置\n"
        "```yaml\n"
        "weights:\n"
        "  LightningDiagnosisTool: 1.0\n"
        "  WindDiagnosisTool: 0.8\n"
        "```\n\n"
        "## 工具调用策略\n\n"
        "| Tool | Weight | Call Condition |\n"
        "|------|--------|---------------|\n"
        "| LightningDiagnosisTool | 1.0 | Always call |\n"
        "| WindDiagnosisTool | 0.8 | Always call |\n",
        encoding="utf-8",
    )
    return SaveSkillCommand(
        mock_llm, mock_session_manager, mock_state_machine, mock_skill_loader,
        skills_dir=skills_dir,
    )


@pytest.mark.asyncio
async def test_save_strategy_success(save_strategy_command: SaveSkillCommand) -> None:
    """save_skill persists skill to file and returns payload."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    session.active_weights = {"ToolA": 1.0}
    session.excluded_tools = ["ToolB"]
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"strategy_name": "my_strategy"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_strategy_command.execute(ctx)]

    assert len(events) == 2
    assert events[-1].event_type == EventType.COMPLETE
    payload = events[-1].payload
    assert payload["skill_name"] == "my_strategy"
    assert "file_path" in payload

    # Verify file was written
    skill_file = save_strategy_command.skills_dir / "my_strategy.md"
    assert skill_file.exists()


@pytest.mark.asyncio
async def test_save_strategy_auto_name(save_strategy_command: SaveSkillCommand) -> None:
    """save_skill generates a name when strategy_name is not provided."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in save_strategy_command.execute(ctx)]

    payload = events[-1].payload
    assert payload["skill_name"].startswith("skill_")


@pytest.mark.asyncio
async def test_save_strategy_invalid_state(save_strategy_command: SaveSkillCommand) -> None:
    """save_skill raises InvalidStateError when state machine rejects."""
    save_strategy_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.SAVE_STRATEGY,
        confidence=0.9,
        parameters={"strategy_name": "test"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in save_strategy_command.execute(ctx)]


@pytest.mark.asyncio
async def test_save_skill_contains_complete_rules(save_strategy_command: SaveSkillCommand) -> None:
    """Generated skill must be self-contained: base body + modifications."""
    session = DiagnosisSession(session_id="s1", line_name="哈哈线", status=SessionStatus.MODIFYING)
    session.active_weights = {"LightningDiagnosisTool": 1.0, "WindDiagnosisTool": 0.8}
    session.excluded_tools = ["LightningDiagnosisTool"]
    session.action_log.append(UserAction(action_type="exclude", parameters={"tool_name": "LightningDiagnosisTool"}))
    session.action_log.append(UserAction(action_type="modify_report", parameters={"instruction": "删除第三章"}))
    session.action_log.append(UserAction(action_type="modify_report", parameters={"instruction": "按照模板调整报告"}))
    ctx = _make_context(session)

    events = [e async for e in save_strategy_command.execute(ctx)]

    # Verify no LLM call was made (code-level build)
    save_strategy_command.llm.chat.assert_not_called()

    # Verify file content
    skill_file = save_strategy_command.skills_dir / "skill_20260101_000000.md"
    # The auto-generated name uses current timestamp, find the actual file
    skill_files = list(save_strategy_command.skills_dir.glob("*.md"))
    # Filter out comprehensive_diagnosis.md
    generated_files = [f for f in skill_files if f.name != "comprehensive_diagnosis.md"]
    assert len(generated_files) == 1
    content = generated_files[0].read_text(encoding="utf-8")

    # Must contain YAML frontmatter
    assert content.startswith("---")
    assert "name:" in content
    assert "description:" in content
    assert "USE THIS SKILL when" in content
    assert "哈哈线" in content

    # Must contain complete base body (not truncated)
    assert "# 输电线路综合诊断" in content
    assert "## 核心算法：加权置信度" in content
    assert "加权置信度 = tool_confidence × tool_weight" in content
    assert "## 工具调用策略" in content

    # Excluded tool must be marked SKIP in the strategy table
    assert "SKIP" in content
    assert "LightningDiagnosisTool" in content

    # Report modification rules must be present
    assert "# 基于本次诊断会话的个性化优化" in content
    assert "删除第三章" in content
    assert "按照模板调整报告" in content
    assert "## 报告撰写规则（必须遵循）" in content


@pytest.mark.asyncio
async def test_save_skill_without_base_file(tmp_path: Path) -> None:
    """save_skill works even when comprehensive_diagnosis.md is missing."""
    mock_llm = AsyncMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_skill_loader = MagicMock()
    mock_state_machine.can_execute.return_value = True
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    # No comprehensive_diagnosis.md created
    cmd = SaveSkillCommand(
        mock_llm, mock_session_manager, mock_state_machine, mock_skill_loader,
        skills_dir=skills_dir,
    )
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    ctx = _make_context(session)

    events = [e async for e in cmd.execute(ctx)]

    assert events[-1].event_type == EventType.COMPLETE
    # Should still generate frontmatter + personalized section
    skill_files = [f for f in skills_dir.glob("*.md") if f.name != "comprehensive_diagnosis.md"]
    assert len(skill_files) == 1
    content = skill_files[0].read_text(encoding="utf-8")
    assert "---" in content
    assert "京西线" in content


# ============================================================================
# DiagnoseCommand
# ============================================================================


@pytest.fixture
def diagnose_command() -> DiagnoseCommand:
    """Return a DiagnoseCommand with mocked dependencies."""
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
    mock_registry.list_tools.return_value = []
    mock_skill_loader.load.return_value = ("# skill", {})
    mock_prompt_builder.build.return_value = "prompt"
    mock_diagnosis_planner.plan.return_value = {
        "tools_to_call": [{"name": "ToolA", "rationale": "test", "parallel": True}],
        "report_structure": ["概述"],
    }
    mock_tool_executor.execute.return_value = {
        "ToolA": ToolOutput(tool_name="ToolA", raw_text="ok"),
    }
    mock_report_composer.compose.return_value = {"report": "# report", "summary": {"fault_type": "雷击", "confidence": 0.85, "primary_tool": "ToolA"}}
    return DiagnoseCommand(
        mock_registry,
        mock_session_manager,
        mock_state_machine,
        mock_event_bus,
        mock_skill_loader,
        mock_prompt_builder,
        mock_diagnosis_planner,
        mock_tool_executor,
        mock_report_composer,
    )


@pytest.mark.asyncio
async def test_diagnose_success(diagnose_command: DiagnoseCommand) -> None:
    """diagnose yields events and completes with report."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    ctx = _make_context(session)

    events = [e async for e in diagnose_command.execute(ctx)]

    assert events[0].event_type == EventType.START
    assert any(e.event_type == EventType.THINKING for e in events)
    assert events[-1].event_type == EventType.COMPLETE
    diagnose_command.session_manager.add_summary.assert_called_once()
    diagnose_command.session_manager.transition.assert_called_with("s1", SessionStatus.MODIFYING)
    # Verify active_template_name is passed to ReportComposer
    call_kwargs = diagnose_command.report_composer.compose.call_args.kwargs
    assert call_kwargs.get("active_template_name") == session.active_template_name


@pytest.mark.asyncio
async def test_diagnose_invalid_state(diagnose_command: DiagnoseCommand) -> None:
    """diagnose raises InvalidStateError when state machine rejects."""
    diagnose_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.COMPLETED)
    ctx = _make_context(session)

    with pytest.raises(InvalidStateError):
        [e async for e in diagnose_command.execute(ctx)]


# ============================================================================
# RecheckToolCommand
# ============================================================================


@pytest.fixture
def recheck_command() -> RecheckToolCommand:
    """Return a RecheckToolCommand with mocked dependencies."""
    mock_registry = MagicMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    mock_registry.list_tool_names.return_value = ["ToolA"]
    mock_registry.execute_tool = AsyncMock(return_value=ToolOutput(tool_name="ToolA", raw_text="rechecked"))
    return RecheckToolCommand(mock_registry, mock_session_manager, mock_state_machine)


@pytest.mark.asyncio
async def test_recheck_tool_success(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool executes successfully with valid params."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    events = [e async for e in recheck_command.execute(ctx)]

    assert events[0].event_type == EventType.START
    assert any(e.event_type == EventType.RESULT for e in events)
    assert events[-1].event_type == EventType.COMPLETE
    recheck_command.session_manager.add_rechecked.assert_called_once_with("s1", "ToolA")


@pytest.mark.asyncio
async def test_recheck_tool_missing_name(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises InvalidStateError when tool_name is missing."""
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError) as exc_info:
        [e async for e in recheck_command.execute(ctx)]

    assert "tool_name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recheck_tool_not_found(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises ToolNotFoundError for unregistered tools."""
    recheck_command.tool_registry.list_tool_names.return_value = ["OtherTool"]
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.MODIFYING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "MissingTool"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(ToolNotFoundError) as exc_info:
        [e async for e in recheck_command.execute(ctx)]

    assert "MissingTool" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recheck_tool_invalid_state(recheck_command: RecheckToolCommand) -> None:
    """recheck_tool raises InvalidStateError when state machine rejects."""
    recheck_command.state_machine.can_execute.return_value = False
    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    intent = Intent(
        intent_type=IntentType.RECHECK_TOOL,
        confidence=0.9,
        parameters={"tool_name": "ToolA"},
    )
    ctx = _make_context(session, intent=intent)

    with pytest.raises(InvalidStateError):
        [e async for e in recheck_command.execute(ctx)]
