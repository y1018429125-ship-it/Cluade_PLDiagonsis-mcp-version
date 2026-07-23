"""Tests for src/core/models.py — model validation, defaults, and serialization."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.core.models import (
    AdapterConfig,
    AdapterType,
    ChapterConfig,
    ConfidenceLevel,
    DiagnosisContext,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisSummary,
    Event,
    EventType,
    ExecutionContext,
    FaultContext,
    Intent,
    IntentType,
    RenderMode,
    SessionStatus,
    Strategy,
    TemplateConfig,
    ToolOutput,
    UserAction,
    DEFAULT_WEIGHTS,
)


# ============================================================================
# Enum sanity checks
# ============================================================================


def test_session_status_has_expected_members() -> None:
    """SessionStatus covers the full lifecycle."""
    members = {s.value for s in SessionStatus}
    assert members == {"pending", "diagnosing", "modifying", "completed", "excluded", "rechecking"}


def test_confidence_level_ordered_correctly() -> None:
    """ConfidenceLevel members are high / medium / low."""
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"


def test_intent_type_covers_all_commands() -> None:
    """IntentType includes every command the system supports."""
    values = {i.value for i in IntentType}
    expected = {
        "diagnose", "exclude_tool", "include_tool", "recheck_tool", "adjust_weight",
        "modify_report", "list_sessions", "switch_session",
        "save_strategy", "load_strategy", "complete", "general",
    }
    assert values == expected


# ============================================================================
# ToolOutput
# ============================================================================


def test_tool_output_defaults() -> None:
    """ToolOutput fills sensible defaults when only tool_name is given."""
    output = ToolOutput(tool_name="TestTool")

    assert output.tool_name == "TestTool"
    assert output.raw_text is None
    assert output.structured_data is None
    assert output.metadata == {}
    assert isinstance(output.timestamp, datetime)


def test_tool_output_full_construction() -> None:
    """ToolOutput accepts all fields explicitly."""
    output = ToolOutput(
        tool_name="T",
        raw_text="raw",
        structured_data={"k": 1},
        metadata={"source": "mcp"},
    )
    assert output.raw_text == "raw"
    assert output.structured_data == {"k": 1}


# ============================================================================
# FaultContext
# ============================================================================


def test_fault_context_requires_line_id_and_name() -> None:
    """FaultContext rejects missing required fields."""
    with pytest.raises(ValidationError):
        FaultContext()  # type: ignore[call-arg]


def test_fault_context_optional_fields_default_to_none_or_empty() -> None:
    """FaultContext optional fields are None or empty collections."""
    ctx = FaultContext(line_id="L1", line_name="LineA")

    assert ctx.tower_id is None
    assert ctx.fault_time is None
    assert ctx.weather_info is None
    assert ctx.scada_data is None
    assert ctx.wave_data is None
    assert ctx.images is None
    assert ctx.additional_info == {}


def test_fault_context_accepts_full_data() -> None:
    """FaultContext round-trips all provided data."""
    ctx = FaultContext(
        line_id="L1",
        line_name="LineA",
        tower_id="T1",
        fault_time=datetime(2024, 1, 1, 12, 0, 0),
        weather_info={"temp": 30},
        scada_data={"I": 100},
        wave_data={"phase": "A"},
        images=["img1.jpg"],
        additional_info={"note": "test"},
    )
    assert ctx.tower_id == "T1"
    assert ctx.fault_time == datetime(2024, 1, 1, 12, 0, 0)
    assert ctx.additional_info == {"note": "test"}


# ============================================================================
# DiagnosisResult
# ============================================================================


def test_diagnosis_result_confidence_clamped_high() -> None:
    """DiagnosisResult rejects confidence above 1.0."""
    with pytest.raises(ValidationError):
        DiagnosisResult(
            fault_type="F",
            confidence=1.5,
            confidence_level=ConfidenceLevel.HIGH,
            tool_name="T",
        )


def test_diagnosis_result_confidence_clamped_low() -> None:
    """DiagnosisResult rejects confidence below 0.0."""
    with pytest.raises(ValidationError):
        DiagnosisResult(
            fault_type="F",
            confidence=-0.1,
            confidence_level=ConfidenceLevel.LOW,
            tool_name="T",
        )


def test_diagnosis_result_defaults() -> None:
    """DiagnosisResult optional fields default to empty."""
    result = DiagnosisResult(
        fault_type="F",
        confidence=0.8,
        confidence_level=ConfidenceLevel.HIGH,
        tool_name="T",
    )
    assert result.evidence == []
    assert result.details == {}


# ============================================================================
# DiagnosisSummary
# ============================================================================


def test_summary_defaults_and_version() -> None:
    """DiagnosisSummary starts at version 1 with empty collections."""
    ctx = FaultContext(line_id="L1", line_name="LineA")
    summary = DiagnosisSummary(fault_context=ctx)

    assert summary.version == 1
    assert summary.parent_version is None
    assert summary.results == []
    assert summary.primary_diagnosis is None
    assert summary.all_evidence == []
    assert summary.confidence_distribution == {}
    assert summary.weights == {}
    assert summary.weighted_scores == {}
    assert summary.excluded_tools == []
    assert summary.rechecked_tools == []


def test_summary_serialization_roundtrip() -> None:
    """DiagnosisSummary serializes and deserializes faithfully."""
    ctx = FaultContext(line_id="L1", line_name="LineA")
    summary = DiagnosisSummary(
        version=2,
        parent_version=1,
        fault_context=ctx,
        results=[
            DiagnosisResult(
                fault_type="Lightning",
                confidence=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                tool_name="LightningDiagnosisTool",
            )
        ],
    )
    data = summary.model_dump()
    restored = DiagnosisSummary.model_validate(data)

    assert restored.version == 2
    assert restored.results[0].fault_type == "Lightning"
    assert restored.fault_context.line_name == "LineA"


# ============================================================================
# DiagnosisSession
# ============================================================================


def test_session_defaults_to_pending_status() -> None:
    """New session starts in PENDING state."""
    session = DiagnosisSession(session_id="s1", line_name="LineA")
    assert session.status == SessionStatus.PENDING


def test_session_copies_default_weights() -> None:
    """Session gets an independent copy of DEFAULT_WEIGHTS."""
    session = DiagnosisSession(session_id="s1", line_name="LineA")
    assert session.active_weights == DEFAULT_WEIGHTS
    assert session.active_weights is not DEFAULT_WEIGHTS


def test_session_post_init_restores_empty_weights() -> None:
    """model_post_init restores default weights when empty dict is passed."""
    session = DiagnosisSession(session_id="s1", line_name="LineA", active_weights={})
    assert session.active_weights == DEFAULT_WEIGHTS


def test_session_post_init_preserves_custom_weights() -> None:
    """model_post_init leaves non-empty custom weights untouched."""
    custom = {"CustomTool": 1.5}
    session = DiagnosisSession(session_id="s1", line_name="LineA", active_weights=custom)
    assert session.active_weights == custom


def test_session_lists_default_to_empty() -> None:
    """New session has empty excluded_tools, rechecked_tools, summaries, action_log."""
    session = DiagnosisSession(session_id="s1", line_name="LineA")
    assert session.excluded_tools == []
    assert session.rechecked_tools == []
    assert session.summaries == []
    assert session.action_log == []
    assert session.current_summary is None
    assert session.custom_strategy_name is None


# ============================================================================
# Intent
# ============================================================================


def test_intent_defaults() -> None:
    """Intent optional fields default to empty."""
    intent = Intent(intent_type=IntentType.DIAGNOSE, confidence=0.95)
    assert intent.parameters == {}
    assert intent.raw_message == ""


def test_intent_confidence_bounds() -> None:
    """Intent confidence must be within [0, 1]."""
    with pytest.raises(ValidationError):
        Intent(intent_type=IntentType.DIAGNOSE, confidence=1.1)


# ============================================================================
# Event
# ============================================================================


def test_event_factory_methods() -> None:
    """Event classmethods produce correctly typed events."""
    e_start = Event.start("s1", "go")
    e_think = Event.thinking("s1", "think")
    e_result = Event.result("s1", {"k": 1})
    e_content = Event.content("s1", "hello")
    e_complete = Event.complete("s1", {"done": True})
    e_error = Event.error("s1", "oops", code="E1")

    assert e_start.event_type == EventType.START
    assert e_think.event_type == EventType.THINKING
    assert e_result.event_type == EventType.RESULT
    assert e_content.event_type == EventType.CONTENT
    assert e_complete.event_type == EventType.COMPLETE
    assert e_error.event_type == EventType.ERROR
    assert e_error.payload["code"] == "E1"


# ============================================================================
# Strategy
# ============================================================================


def test_strategy_defaults() -> None:
    """Strategy fills empty collections and None for optionals."""
    strategy = Strategy(name="Default")
    assert strategy.description is None
    assert strategy.tool_weights == {}
    assert strategy.excluded_tools == []
    assert strategy.template_name is None
    assert strategy.chapter_order is None


# ============================================================================
# ChapterConfig / TemplateConfig
# ============================================================================


def test_chapter_config_defaults() -> None:
    """ChapterConfig defaults to required=True and MIXED render mode."""
    ch = ChapterConfig(chapter_type="summary", title="Summary")
    assert ch.required is True
    assert ch.render_mode == RenderMode.MIXED
    assert ch.data_sources == []


def test_template_config_defaults() -> None:
    """TemplateConfig defaults to empty chapters and weights."""
    tmpl = TemplateConfig(name="Standard")
    assert tmpl.source_file is None
    assert tmpl.chapters == []
    assert tmpl.default_weights == {}


# ============================================================================
# DiagnosisContext / ExecutionContext
# ============================================================================


def test_diagnosis_context_defaults() -> None:
    """DiagnosisContext optional fields default to empty or None."""
    ctx = DiagnosisContext(session_id="s1", line_name="LineA")
    assert ctx.weights == {}
    assert ctx.excluded_tools == []
    assert ctx.rechecked_tools == []
    assert ctx.fault_context is None


def test_execution_context_requires_session_and_message() -> None:
    """ExecutionContext requires session and user_message."""
    session = DiagnosisSession(session_id="s1", line_name="LineA")
    diag_ctx = DiagnosisContext(session_id="s1", line_name="LineA")

    exec_ctx = ExecutionContext(
        session=session,
        diagnosis_ctx=diag_ctx,
        user_message=" diagnose ",
    )
    assert exec_ctx.session.session_id == "s1"
    assert exec_ctx.user_message == " diagnose "
    assert exec_ctx.intent is None


# ============================================================================
# AdapterConfig
# ============================================================================


def test_adapter_config_defaults() -> None:
    """AdapterConfig defaults to empty config dict."""
    ac = AdapterConfig(type=AdapterType.MCP)
    assert ac.config == {}
