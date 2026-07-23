"""Tests for src/infrastructure/adapters/mcp_adapter.py — HTTP client mode."""

import httpx
import pytest
from unittest.mock import MagicMock, patch

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.mcp_adapter import MCPToolAdapter


# ============================================================================
# Properties
# ============================================================================


def test_mcp_adapter_properties_reflect_config() -> None:
    """MCPToolAdapter exposes config values through its properties."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
        "description": "Detects lightning",
        "category": "electrical",
        "url": "http://localhost:8001",
    })

    assert adapter.name == "LightningDiagnosisTool"
    assert adapter.display_name == "Lightning"
    assert adapter.description == "Detects lightning"
    assert adapter.category == "electrical"
    assert adapter.url == "http://localhost:8001"


def test_mcp_adapter_defaults_when_config_sparse() -> None:
    """MCPToolAdapter fills sensible defaults for missing config keys."""
    adapter = MCPToolAdapter({})

    assert adapter.name == "unknown"
    assert adapter.display_name == "unknown"
    assert adapter.description == ""
    assert adapter.category == "unknown"
    assert adapter.url == ""
    assert adapter.timeout == 30


# ============================================================================
# execute — mocked HTTP responses
# ============================================================================


@pytest.mark.asyncio
async def test_execute_returns_tool_output() -> None:
    """execute() returns a ToolOutput with structured data on success."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
        "url": "http://localhost:8001",
    })

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "raw_text": "雷电监测数据分析",
        "structured_data": {
            "fault_type": "雷击跳闸",
            "confidence": 0.85,
            "longitude": 114.3055,
        },
        "metadata": {"source": "雷电定位系统"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        context = FaultContext(line_id="L1", line_name="LineA")
        output = await adapter.execute(context)

    assert isinstance(output, ToolOutput)
    assert output.tool_name == "LightningDiagnosisTool"
    assert output.structured_data is not None
    assert "longitude" in output.structured_data
    assert output.structured_data["fault_type"] == "雷击跳闸"


@pytest.mark.asyncio
async def test_execute_returns_error_on_http_failure() -> None:
    """execute() returns error structured data when HTTP call fails."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
        "url": "http://localhost:8001",
    })

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        context = FaultContext(line_id="L1", line_name="LineA")
        output = await adapter.execute(context)

    assert "Connection refused" in output.structured_data["error"]
    assert output.structured_data["fault_type"] == "未知"
    assert output.structured_data["confidence"] == 0.0
    assert output.metadata["error"] is True


@pytest.mark.asyncio
async def test_execute_includes_raw_text() -> None:
    """execute() populates raw_text from the HTTP response."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "display_name": "Lightning",
        "url": "http://localhost:8001",
    })

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "raw_text": "雷电监测数据分析",
        "structured_data": {},
        "metadata": {},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        context = FaultContext(line_id="L1", line_name="LineA")
        output = await adapter.execute(context)

    assert output.raw_text == "雷电监测数据分析"


@pytest.mark.asyncio
async def test_execute_includes_metadata() -> None:
    """execute() tags output with metadata from the HTTP response."""
    adapter = MCPToolAdapter({
        "tool_name": "LightningDiagnosisTool",
        "url": "http://localhost:8001",
    })

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "raw_text": "",
        "structured_data": {},
        "metadata": {"source": "雷电定位系统"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        context = FaultContext(line_id="L1", line_name="LineA")
        output = await adapter.execute(context)

    assert output.metadata.get("source") == "雷电定位系统"


# ============================================================================
# close
# ============================================================================


@pytest.mark.asyncio
async def test_close_aclose_client() -> None:
    """close() closes the underlying httpx client."""
    adapter = MCPToolAdapter({
        "tool_name": "T",
        "url": "http://localhost:8001",
    })

    async def mock_aclose():
        pass

    mock_client = MagicMock()
    mock_client.aclose = mock_aclose
    adapter._client = mock_client

    await adapter.close()

    assert adapter._client is None
