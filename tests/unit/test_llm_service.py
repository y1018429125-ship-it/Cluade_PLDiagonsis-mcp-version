"""Tests for src/infrastructure/llm_service.py — mocked AsyncOpenAI."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import LLMConfig
from src.core.exceptions import LLMServiceError
from src.core.models import Intent, IntentType
from src.infrastructure.llm_service import LLMService


@pytest.fixture
def llm_config() -> LLMConfig:
    """Return a minimal LLMConfig for testing."""
    return LLMConfig(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
        base_url="https://test.example.com/v1",
        temperature=0.3,
        max_tokens=1024,
    )


@pytest.fixture
def llm_service(llm_config: LLMConfig) -> LLMService:
    """Return an LLMService wired to the test config."""
    return LLMService(llm_config)


# ============================================================================
# chat
# ============================================================================


@pytest.mark.asyncio
async def test_chat_returns_content(llm_service: LLMService) -> None:
    """chat() returns the message content from the LLM response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "hello world"

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await llm_service.chat([{"role": "user", "content": "hi"}])

    assert result == "hello world"


@pytest.mark.asyncio
async def test_chat_uses_config_defaults(llm_service: LLMService) -> None:
    """chat() passes temperature and max_tokens from config when not overridden."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    await llm_service.chat([{"role": "user", "content": "test"}])

    call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_chat_allows_kwargs_override(llm_service: LLMService) -> None:
    """chat() lets kwargs override config defaults."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    await llm_service.chat([{"role": "user", "content": "test"}], temperature=0.9, max_tokens=64)

    call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.9
    assert call_kwargs["max_tokens"] == 64


@pytest.mark.asyncio
async def test_chat_raises_on_failure(llm_service: LLMService) -> None:
    """chat() raises LLMServiceError when the API call fails."""
    llm_service.client.chat.completions.create = AsyncMock(side_effect=RuntimeError("network error"))

    with pytest.raises(LLMServiceError) as exc_info:
        await llm_service.chat([{"role": "user", "content": "test"}])

    assert "network error" in str(exc_info.value)


# ============================================================================
# structured_output
# ============================================================================


@pytest.mark.asyncio
async def test_structured_output_returns_parsed_model(llm_service: LLMService) -> None:
    """structured_output() parses JSON response into the given schema."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"intent_type": "diagnose", "confidence": 0.95}'

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await llm_service.structured_output(
        [{"role": "user", "content": "test"}], Intent
    )

    assert isinstance(result, Intent)
    assert result.intent_type == IntentType.DIAGNOSE
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_structured_output_uses_json_mode(llm_service: LLMService) -> None:
    """structured_output() sets response_format to json_object."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"intent_type": "general", "confidence": 0.5}'

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    await llm_service.structured_output([{"role": "user", "content": "test"}], Intent)

    call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_structured_output_raises_on_invalid_json(llm_service: LLMService) -> None:
    """structured_output() raises LLMServiceError for non-JSON responses."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json"

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    with pytest.raises(LLMServiceError) as exc_info:
        await llm_service.structured_output([{"role": "user", "content": "test"}], Intent)

    assert "格式错误" in str(exc_info.value)


@pytest.mark.asyncio
async def test_structured_output_raises_on_api_error(llm_service: LLMService) -> None:
    """structured_output() raises LLMServiceError when the API call fails."""
    llm_service.client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(LLMServiceError) as exc_info:
        await llm_service.structured_output([{"role": "user", "content": "test"}], Intent)

    assert "boom" in str(exc_info.value)


# ============================================================================
# intent_classification
# ============================================================================


@pytest.mark.asyncio
async def test_intent_classification_returns_intent(llm_service: LLMService) -> None:
    """intent_classification() returns an Intent for the message."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"intent_type": "diagnose", "confidence": 0.9}'

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await llm_service.intent_classification("220kV线路跳闸")

    assert isinstance(result, Intent)
    assert result.intent_type == IntentType.DIAGNOSE


@pytest.mark.asyncio
async def test_intent_classification_includes_session_context(llm_service: LLMService) -> None:
    """intent_classification() embeds session_context in the prompt."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"intent_type": "general", "confidence": 0.5}'

    llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

    await llm_service.intent_classification("hello", session_context={"line": "京西线"})

    call_messages = llm_service.client.chat.completions.create.call_args.kwargs["messages"]
    prompt = call_messages[1]["content"]
    assert "京西线" in prompt
