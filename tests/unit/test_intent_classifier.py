"""Tests for src/domain/intent_classifier.py — mocked LLM interactions."""

from unittest.mock import AsyncMock

import pytest

from src.core.models import DiagnosisSession, Intent, IntentType, SessionStatus
from src.core.exceptions import IntentClassificationError
from src.domain.intent_classifier import IntentClassifier
from src.infrastructure.llm_service import LLMService


@pytest.fixture
def mock_llm_service() -> AsyncMock:
    """Return a mocked LLMService."""
    return AsyncMock(spec=LLMService)


@pytest.fixture
def classifier(mock_llm_service: AsyncMock) -> IntentClassifier:
    """Return an IntentClassifier wired to the mock LLM."""
    return IntentClassifier(mock_llm_service)


# ============================================================================
# classify — happy path
# ============================================================================


@pytest.mark.asyncio
async def test_classify_returns_intent_from_llm(classifier: IntentClassifier, mock_llm_service: AsyncMock) -> None:
    """classify() returns the Intent produced by the LLM when confidence is high."""
    mock_llm_service.structured_output.return_value = Intent(
        intent_type=IntentType.DIAGNOSE,
        confidence=0.95,
        raw_message="",
    )

    result = await classifier.classify("220kV京西线跳闸了")

    assert result.intent_type == IntentType.DIAGNOSE
    assert result.confidence == 0.95
    assert result.raw_message == "220kV京西线跳闸了"


@pytest.mark.asyncio
async def test_classify_fallbacks_when_confidence_low(classifier: IntentClassifier, mock_llm_service: AsyncMock) -> None:
    """classify() falls back to GENERAL when LLM confidence is below threshold."""
    mock_llm_service.structured_output.return_value = Intent(
        intent_type=IntentType.DIAGNOSE,
        confidence=0.5,
        raw_message="",
    )

    result = await classifier.classify("随便聊聊")

    assert result.intent_type == IntentType.GENERAL
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_classify_fallbacks_on_exception(classifier: IntentClassifier, mock_llm_service: AsyncMock) -> None:
    """classify() falls back to GENERAL when the LLM raises an exception."""
    mock_llm_service.structured_output.side_effect = RuntimeError("LLM down")

    result = await classifier.classify("hello")

    assert result.intent_type == IntentType.GENERAL
    assert result.confidence == 1.0
    assert result.raw_message == "hello"


# ============================================================================
# classify — with session context
# ============================================================================


@pytest.mark.asyncio
async def test_classify_builds_session_context(classifier: IntentClassifier, mock_llm_service: AsyncMock) -> None:
    """classify() passes session context to the LLM prompt."""
    mock_llm_service.structured_output.return_value = Intent(
        intent_type=IntentType.ADJUST_WEIGHT,
        confidence=0.9,
    )

    session = DiagnosisSession(session_id="s1", line_name="京西线", status=SessionStatus.DIAGNOSING)
    await classifier.classify("提高权重", session)

    call_args = mock_llm_service.structured_output.call_args[0][0]
    assert any("京西线" in str(msg) for msg in call_args)


@pytest.mark.asyncio
async def test_classify_handles_no_session(classifier: IntentClassifier, mock_llm_service: AsyncMock) -> None:
    """classify() works when no session is provided."""
    mock_llm_service.structured_output.return_value = Intent(
        intent_type=IntentType.GENERAL,
        confidence=0.8,
    )

    result = await classifier.classify("help")

    call_args = mock_llm_service.structured_output.call_args[0][0]
    assert any("无活跃会话" in str(msg) for msg in call_args)
    assert result.intent_type == IntentType.GENERAL


# ============================================================================
# _build_system_prompt
# ============================================================================


def test_build_system_prompt_lists_all_intent_types(classifier: IntentClassifier) -> None:
    """_build_system_prompt() enumerates every IntentType."""
    prompt = classifier._build_system_prompt()
    for intent_type in IntentType:
        assert intent_type.value in prompt


def test_build_system_prompt_contains_json_format(classifier: IntentClassifier) -> None:
    """_build_system_prompt() instructs the model to return JSON."""
    prompt = classifier._build_system_prompt()
    assert "JSON" in prompt
    assert "intent_type" in prompt
    assert "confidence" in prompt


# ============================================================================
# _build_session_context
# ============================================================================


def test_build_session_context_returns_no_session_when_none(classifier: IntentClassifier) -> None:
    """_build_session_context() returns a no-session message when session is None."""
    assert classifier._build_session_context(None) == "当前无活跃会话"


def test_build_session_context_includes_session_details(classifier: IntentClassifier) -> None:
    """_build_session_context() embeds session id, line name, status, weights."""
    session = DiagnosisSession(
        session_id="s1",
        line_name="京西线",
        status=SessionStatus.DIAGNOSING,
        excluded_tools=["ToolA"],
    )
    ctx = classifier._build_session_context(session)
    assert "s1" in ctx
    assert "京西线" in ctx
    assert "diagnosing" in ctx
    assert "ToolA" in ctx
