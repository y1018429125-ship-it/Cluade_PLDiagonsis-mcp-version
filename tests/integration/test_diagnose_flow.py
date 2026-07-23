"""Integration tests for the full diagnose flow with mocked MCP adapters."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import (
    DiagnosisSession,
    DiagnosisSummary,
    EventType,
    FaultContext,
    SessionStatus,
    ToolOutput,
)
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.weight_engine import WeightEngine
from src.infrastructure.adapters.base import ToolAdapter
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.event_bus import EventBus


# ============================================================================
# Helpers
# ============================================================================


class _FakeMCPAdapter(ToolAdapter):
    """Fake MCP-style adapter for integration testing."""

    def __init__(self, name: str, confidence: float = 0.75):
        super().__init__({})
        self._name = name
        self._confidence = confidence

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return f"Display {self._name}"

    @property
    def description(self) -> str:
        return f"Fake {self._name}"

    @property
    def category(self) -> str:
        return "integration_test"

    async def execute(self, context: FaultContext) -> ToolOutput:
        return ToolOutput(
            tool_name=self._name,
            raw_text=f"{self._name} result",
            structured_data={"confidence": self._confidence, "result": "ok"},
        )


# ============================================================================
# End-to-end diagnose flow
# ============================================================================


@pytest.mark.asyncio
async def test_full_diagnose_flow_with_mocked_tools(app_config) -> None:
    """A complete diagnosis: create session -> run tools -> compute summary."""
    # Arrange
    event_bus = EventBus()
    state_machine = StateMachine(event_bus)
    session_manager = SessionManager(event_bus, state_machine)
    weight_engine = WeightEngine()

    registry = ToolRegistry(app_config)
    registry._adapters["LightningDiagnosisTool"] = _FakeMCPAdapter("LightningDiagnosisTool", 0.9)
    registry._adapters["WindDiagnosisTool"] = _FakeMCPAdapter("WindDiagnosisTool", 0.5)

    # Act — create session
    session = session_manager.create("220kV京西线")
    assert session.status == SessionStatus.PENDING

    # Act — transition to diagnosing
    session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)
    assert session.status == SessionStatus.DIAGNOSING

    # Act — run tools in parallel
    fault_ctx = FaultContext(
        line_id="LN-001",
        line_name=session.line_name,
    )
    tool_outputs = await registry.execute_parallel(
        ["LightningDiagnosisTool", "WindDiagnosisTool"],
        fault_ctx,
    )

    # Act — compute weighted summary
    summary = weight_engine.compute(tool_outputs, session.active_weights)

    # Act — attach summary and transition
    session_manager.add_summary(session.session_id, summary)
    session_manager.transition(session.session_id, SessionStatus.MODIFYING)
    session_manager.transition(session.session_id, SessionStatus.COMPLETED)

    # Assert
    assert session.status == SessionStatus.COMPLETED
    assert session.current_summary is not None
    assert session.current_summary.primary_diagnosis is not None
    # Lightning has higher confidence and weight
    assert session.current_summary.primary_diagnosis.tool_name == "LightningDiagnosisTool"
    assert len(session.summaries) == 1


@pytest.mark.asyncio
async def test_diagnose_flow_with_tool_exclusion(app_config) -> None:
    """Excluded tools are skipped during parallel execution."""
    # Arrange
    event_bus = EventBus()
    state_machine = StateMachine(event_bus)
    session_manager = SessionManager(event_bus, state_machine)
    weight_engine = WeightEngine()

    registry = ToolRegistry(app_config)
    registry._adapters["ToolA"] = _FakeMCPAdapter("ToolA", 0.8)
    registry._adapters["ToolB"] = _FakeMCPAdapter("ToolB", 0.6)

    session = session_manager.create("京西线")
    session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)

    # Exclude ToolB
    session_manager.exclude_tool(session.session_id, "ToolB")

    fault_ctx = FaultContext(line_id="L1", line_name="京西线")
    available_tools = [t for t in ["ToolA", "ToolB"] if t not in session.excluded_tools]
    outputs = await registry.execute_parallel(available_tools, fault_ctx)

    summary = weight_engine.compute(outputs, session.active_weights)
    session_manager.add_summary(session.session_id, summary)

    # Assert
    assert "ToolB" not in outputs
    assert summary.primary_diagnosis.tool_name == "ToolA"


@pytest.mark.asyncio
async def test_diagnose_flow_with_weight_adjustment(app_config) -> None:
    """Adjusted weights change the primary diagnosis selection."""
    # Arrange
    event_bus = EventBus()
    state_machine = StateMachine(event_bus)
    session_manager = SessionManager(event_bus, state_machine)
    weight_engine = WeightEngine()

    registry = ToolRegistry(app_config)
    # ToolA: confidence 0.6, ToolB: confidence 0.5
    registry._adapters["ToolA"] = _FakeMCPAdapter("ToolA", 0.6)
    registry._adapters["ToolB"] = _FakeMCPAdapter("ToolB", 0.5)

    session = session_manager.create("京西线")
    session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)

    # Boost ToolB weight so it wins despite lower raw confidence
    session_manager.update_weights(session.session_id, {"ToolA": 0.5, "ToolB": 2.0})

    fault_ctx = FaultContext(line_id="L1", line_name="京西线")
    outputs = await registry.execute_parallel(["ToolA", "ToolB"], fault_ctx)
    summary = weight_engine.compute(outputs, session.active_weights)

    # Assert — weighted score: ToolA=0.3, ToolB=1.0
    assert summary.primary_diagnosis.tool_name == "ToolB"
    assert summary.weighted_scores["ToolA"] == 0.3
    assert summary.weighted_scores["ToolB"] == 1.0


@pytest.mark.asyncio
async def test_diagnose_flow_error_isolation(app_config) -> None:
    """A failing tool does not crash the entire diagnosis."""
    # Arrange
    event_bus = EventBus()
    state_machine = StateMachine(event_bus)
    session_manager = SessionManager(event_bus, state_machine)
    weight_engine = WeightEngine()

    registry = ToolRegistry(app_config)
    registry._adapters["GoodTool"] = _FakeMCPAdapter("GoodTool", 0.8)

    class _FailingAdapter(ToolAdapter):
        def __init__(self):
            super().__init__({})

        @property
        def name(self) -> str:
            return "BadTool"

        @property
        def display_name(self) -> str:
            return "BadTool"

        @property
        def description(self) -> str:
            return "Fails"

        @property
        def category(self) -> str:
            return "test"

        async def execute(self, context: FaultContext) -> ToolOutput:
            raise RuntimeError("forced failure")

    registry._adapters["BadTool"] = _FailingAdapter()

    session = session_manager.create("京西线")
    session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)

    fault_ctx = FaultContext(line_id="L1", line_name="京西线")
    outputs = await registry.execute_parallel(["GoodTool", "BadTool"], fault_ctx)
    summary = weight_engine.compute(outputs, session.active_weights)

    # Assert
    assert "GoodTool" in outputs
    assert "BadTool" in outputs
    assert outputs["BadTool"].raw_text.startswith("执行失败")
    assert summary.primary_diagnosis.tool_name == "GoodTool"


@pytest.mark.asyncio
async def test_event_bus_receives_during_flow(app_config) -> None:
    """State transitions publish events that subscribers receive."""
    event_bus = EventBus()
    state_machine = StateMachine(event_bus)
    session_manager = SessionManager(event_bus, state_machine)

    received: list = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe_session("s1", handler)

    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.PENDING)
    session_manager._sessions["s1"] = session
    session_manager._active_session_id = "s1"

    session_manager.transition("s1", SessionStatus.DIAGNOSING)

    import asyncio
    await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].event_type == EventType.STATUS
