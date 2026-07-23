"""Tests for src/application/context.py — ExecutionContext construction."""

from src.core.models import (
    DiagnosisContext,
    DiagnosisSession,
    ExecutionContext,
    SessionStatus,
)
from src.application.context import ContextBuilder


# ============================================================================
# build
# ============================================================================


def test_build_returns_execution_context() -> None:
    """build() returns an ExecutionContext instance."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "diagnose")
    assert isinstance(result, ExecutionContext)


def test_build_copies_session_reference() -> None:
    """build() embeds the provided session object."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "msg")
    assert result.session is session


def test_build_copies_user_message() -> None:
    """build() preserves the user_message verbatim."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "请诊断故障")
    assert result.user_message == "请诊断故障"


def test_build_creates_diagnosis_context_with_session_id() -> None:
    """build() creates a DiagnosisContext whose session_id matches."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "msg")
    assert result.diagnosis_ctx.session_id == "s1"


def test_build_creates_diagnosis_context_with_line_name() -> None:
    """build() creates a DiagnosisContext whose line_name matches."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "msg")
    assert result.diagnosis_ctx.line_name == "京西线"


def test_build_copies_weights_into_diagnosis_context() -> None:
    """build() copies active_weights into DiagnosisContext.weights."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        active_weights={"ToolA": 1.5},
    )
    result = ContextBuilder.build(session, "msg")
    assert result.diagnosis_ctx.weights == {"ToolA": 1.5}


def test_build_copies_excluded_tools_into_diagnosis_context() -> None:
    """build() copies excluded_tools into DiagnosisContext.excluded_tools."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        excluded_tools=["ToolA"],
    )
    result = ContextBuilder.build(session, "msg")
    assert result.diagnosis_ctx.excluded_tools == ["ToolA"]


def test_build_copies_rechecked_tools_into_diagnosis_context() -> None:
    """build() copies rechecked_tools into DiagnosisContext.rechecked_tools."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        rechecked_tools=["ToolB"],
    )
    result = ContextBuilder.build(session, "msg")
    assert result.diagnosis_ctx.rechecked_tools == ["ToolB"]


def test_build_weights_are_independent_copy() -> None:
    """build() does not share the weights dict with the session."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        active_weights={"ToolA": 1.0},
    )
    result = ContextBuilder.build(session, "msg")
    result.diagnosis_ctx.weights["ToolA"] = 2.0
    assert session.active_weights["ToolA"] == 1.0


def test_build_excluded_tools_are_independent_copy() -> None:
    """build() does not share the excluded_tools list with the session."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        excluded_tools=["ToolA"],
    )
    result = ContextBuilder.build(session, "msg")
    result.diagnosis_ctx.excluded_tools.append("ToolB")
    assert session.excluded_tools == ["ToolA"]


def test_build_rechecked_tools_are_independent_copy() -> None:
    """build() does not share the rechecked_tools list with the session."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        rechecked_tools=["ToolA"],
    )
    result = ContextBuilder.build(session, "msg")
    result.diagnosis_ctx.rechecked_tools.append("ToolB")
    assert session.rechecked_tools == ["ToolA"]


def test_build_defaults_intent_to_none() -> None:
    """build() leaves intent as None when not provided."""
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    result = ContextBuilder.build(session, "msg")
    assert result.intent is None


def test_build_passes_kwargs_to_execution_context() -> None:
    """build() forwards extra kwargs to ExecutionContext."""
    from src.core.models import Intent, IntentType
    session = DiagnosisSession(session_id="s1", line_name="京西线")
    intent = Intent(intent_type=IntentType.DIAGNOSE, confidence=0.9)
    result = ContextBuilder.build(session, "msg", intent=intent)
    assert result.intent == intent
