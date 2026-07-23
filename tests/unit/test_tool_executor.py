"""Tests for src/domain/tool_executor.py — parallel/sequential tool execution."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import ToolOutput
from src.domain.tool_executor import ToolExecutor


# ============================================================================
# execute — parallel tools
# ============================================================================


@pytest.mark.asyncio
async def test_execute_parallel_tools() -> None:
    """并行工具应通过 asyncio.gather 同时执行，返回所有结果。"""
    mock_registry = MagicMock()
    mock_registry.execute_tool = AsyncMock(side_effect=lambda name, ctx: ToolOutput(
        tool_name=name,
        raw_text=f"Result from {name}",
    ))

    executor = ToolExecutor(mock_registry)
    plan = {
        "tools_to_call": [
            {"name": "ToolA", "parallel": True},
            {"name": "ToolB", "parallel": True},
            {"name": "ToolC"},  # parallel 缺失，默认并行
        ]
    }

    results = await executor.execute(plan, "fake_context")

    assert set(results.keys()) == {"ToolA", "ToolB", "ToolC"}
    assert results["ToolA"].tool_name == "ToolA"
    assert results["ToolA"].raw_text == "Result from ToolA"
    assert results["ToolB"].tool_name == "ToolB"
    assert results["ToolC"].tool_name == "ToolC"

    # 验证每个工具都被调用了一次
    assert mock_registry.execute_tool.call_count == 3


@pytest.mark.asyncio
async def test_execute_unknown_tool_skipped() -> None:
    """未知工具执行失败时应被优雅处理，返回错误信息而不是抛出异常。"""
    mock_registry = MagicMock()

    async def _fake_execute(name: str, ctx: object) -> ToolOutput:
        if name == "UnknownTool":
            raise RuntimeError("工具不存在")
        return ToolOutput(tool_name=name, raw_text=f"Result from {name}")

    mock_registry.execute_tool = AsyncMock(side_effect=_fake_execute)

    executor = ToolExecutor(mock_registry)
    plan = {
        "tools_to_call": [
            {"name": "KnownTool", "parallel": True},
            {"name": "UnknownTool", "parallel": True},
        ]
    }

    results = await executor.execute(plan, "fake_context")

    # KnownTool 正常返回
    assert "KnownTool" in results
    assert results["KnownTool"].raw_text == "Result from KnownTool"

    # UnknownTool 因为异常被 gather 捕获后跳过，不会出现在结果中
    # （gather 的 return_exceptions=True 会将异常作为结果返回，
    #  execute 方法中会检查 isinstance(result, Exception) 并跳过）
    assert "UnknownTool" not in results
