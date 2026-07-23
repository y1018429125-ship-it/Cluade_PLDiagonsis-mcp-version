"""pytest fixtures for PLDiagnosis test suite."""

from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import (
    AdapterType,
    AdapterConfig,
    ConfidenceLevel,
    DiagnosisSession,
    EventType,
    FaultContext,
    SessionStatus,
    ToolConfig,
    ToolOutput,
)
from src.core.config import AppConfig
from src.domain.state_machine import StateMachine
from src.domain.session_manager import SessionManager
from src.infrastructure.adapters.base import ToolAdapter
from src.infrastructure.event_bus import EventBus


# ---------------------------------------------------------------------------
# Core infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> EventBus:
    """Return a fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def state_machine(event_bus: EventBus) -> StateMachine:
    """Return a StateMachine wired to the event_bus fixture."""
    return StateMachine(event_bus)


@pytest.fixture
def session_manager(event_bus: EventBus, state_machine: StateMachine) -> SessionManager:
    """Return a SessionManager wired to event_bus and state_machine."""
    return SessionManager(event_bus, state_machine)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fault_context() -> FaultContext:
    """Return a representative FaultContext for tests."""
    return FaultContext(
        line_id="LN-001",
        line_name="京西线",
        tower_id="T-1024",
        fault_time=datetime(2024, 6, 15, 14, 30, 0),
        weather_info={"temperature": 28.5, "condition": "雷阵雨"},
        scada_data={"current": 120.0, "voltage": 220.0},
        additional_info={"operator": "张三"},
    )


@pytest.fixture
def sample_session() -> DiagnosisSession:
    """Return a pending DiagnosisSession with default weights."""
    return DiagnosisSession(
        session_id="sess_test001",
        line_name="京西线",
        status=SessionStatus.PENDING,
    )


# ---------------------------------------------------------------------------
# Mock adapter fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tool_adapter() -> ToolAdapter:
    """Return a mock ToolAdapter that yields deterministic ToolOutput."""

    class _MockAdapter(ToolAdapter):
        def __init__(self, name: str, category: str = "test"):
            super().__init__({})
            self._name = name
            self._category = category

        @property
        def name(self) -> str:
            return self._name

        @property
        def display_name(self) -> str:
            return f"Display {self._name}"

        @property
        def description(self) -> str:
            return f"Description for {self._name}"

        @property
        def category(self) -> str:
            return self._category

        async def execute(self, context: FaultContext) -> ToolOutput:
            return ToolOutput(
                tool_name=self._name,
                raw_text=f"Result from {self._name}",
                structured_data={"confidence": 0.75, "result": "ok"},
            )

    return _MockAdapter


@pytest.fixture
def failing_tool_adapter() -> ToolAdapter:
    """Return a mock ToolAdapter that always raises on execute."""

    class _FailingAdapter(ToolAdapter):
        def __init__(self, name: str):
            super().__init__({})
            self._name = name

        @property
        def name(self) -> str:
            return self._name

        @property
        def display_name(self) -> str:
            return self._name

        @property
        def description(self) -> str:
            return "Always fails"

        @property
        def category(self) -> str:
            return "test"

        async def execute(self, context: FaultContext) -> ToolOutput:
            raise RuntimeError(f"{self._name} forced failure")

    return _FailingAdapter


# ---------------------------------------------------------------------------
# AppConfig fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app_config(tmp_path) -> AppConfig:
    """Return an AppConfig with a temporary tools directory."""
    config = AppConfig()
    config.tools.config_directory = str(tmp_path / "tools")
    return config
