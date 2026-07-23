import httpx
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.adapters.mcp_adapter import MCPToolAdapter
from src.core.models import FaultContext, ToolOutput


@pytest.fixture
def adapter():
    config = {
        "tool_name": "LightningDiagnosisTool",
        "display_name": "雷电诊断",
        "description": "基于雷电定位系统的故障诊断",
        "category": "电气",
        "url": "http://localhost:8001",
        "timeout": 30,
    }
    return MCPToolAdapter(config)


def test_adapter_properties(adapter):
    assert adapter.name == "LightningDiagnosisTool"
    assert adapter.display_name == "雷电诊断"
    assert adapter.url == "http://localhost:8001"


@pytest.mark.asyncio
async def test_adapter_execute_success(adapter):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tool_name": "LightningDiagnosisTool",
        "raw_text": "雷电监测数据分析",
        "structured_data": {
            "fault_type": "雷击跳闸",
            "confidence": 0.85,
        },
        "metadata": {"source": "雷电定位系统"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        ctx = FaultContext(line_id="line_1", line_name="武汉线")
        result = await adapter.execute(ctx)

    assert isinstance(result, ToolOutput)
    assert result.tool_name == "LightningDiagnosisTool"
    assert result.structured_data["fault_type"] == "雷击跳闸"
    assert result.structured_data["confidence"] == 0.85


@pytest.mark.asyncio
async def test_adapter_execute_http_error(adapter):
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        ctx = FaultContext(line_id="line_1", line_name="武汉线")
        result = await adapter.execute(ctx)

    assert "Connection refused" in result.structured_data["error"]
    assert result.structured_data["confidence"] == 0.0


@pytest.mark.asyncio
async def test_adapter_execute_status_error(adapter):
    """Test handling of HTTP 4xx/5xx responses"""
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        ctx = FaultContext(line_id="line_1", line_name="武汉线")
        result = await adapter.execute(ctx)

    assert isinstance(result, ToolOutput)
    assert result.structured_data["confidence"] == 0.0
    assert "error" in result.structured_data


@pytest.mark.asyncio
async def test_adapter_close_no_client(adapter):
    """Test close() when client was never created"""
    await adapter.close()
    assert adapter._client is None
