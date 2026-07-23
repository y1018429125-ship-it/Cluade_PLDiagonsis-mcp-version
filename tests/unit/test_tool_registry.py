"""Tests for src/infrastructure/adapters/registry.py — loading, lookup, parallel execution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import ToolNotFoundError
from src.core.models import AdapterConfig, AdapterType, FaultContext, ToolConfig, ToolOutput
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.adapters.base import ToolAdapter


# ============================================================================
# get_adapter / list_tools / list_tool_names
# ============================================================================


def test_get_adapter_returns_registered_adapter(app_config, mock_tool_adapter) -> None:
    """get_adapter() returns the adapter previously registered."""
    registry = ToolRegistry(app_config)
    adapter = mock_tool_adapter("MockTool")
    registry._adapters["MockTool"] = adapter

    result = registry.get_adapter("MockTool")
    assert result is adapter


def test_get_adapter_raises_when_tool_missing(app_config) -> None:
    """get_adapter() raises ToolNotFoundError for unregistered tools."""
    registry = ToolRegistry(app_config)
    with pytest.raises(ToolNotFoundError) as exc_info:
        registry.get_adapter("MissingTool")
    assert "MissingTool" in str(exc_info.value)


def test_list_tools_returns_all_adapters(app_config, mock_tool_adapter) -> None:
    """list_tools() returns every registered adapter."""
    registry = ToolRegistry(app_config)
    a1 = mock_tool_adapter("ToolA")
    a2 = mock_tool_adapter("ToolB")
    registry._adapters["ToolA"] = a1
    registry._adapters["ToolB"] = a2

    assert set(registry.list_tools()) == {a1, a2}


def test_list_tool_names_returns_all_names(app_config, mock_tool_adapter) -> None:
    """list_tool_names() returns every registered tool name."""
    registry = ToolRegistry(app_config)
    registry._adapters["ToolA"] = mock_tool_adapter("ToolA")
    registry._adapters["ToolB"] = mock_tool_adapter("ToolB")

    assert set(registry.list_tool_names()) == {"ToolA", "ToolB"}


def test_get_tool_config_returns_config_when_present(app_config) -> None:
    """get_tool_config() returns the stored ToolConfig."""
    registry = ToolRegistry(app_config)
    cfg = ToolConfig(
        name="TestTool",
        display_name="Test",
        description="desc",
        category="cat",
        adapter=AdapterConfig(type=AdapterType.MCP),
    )
    registry._configs["TestTool"] = cfg
    assert registry.get_tool_config("TestTool") is cfg


def test_get_tool_config_returns_none_when_missing(app_config) -> None:
    """get_tool_config() returns None for unregistered tools."""
    registry = ToolRegistry(app_config)
    assert registry.get_tool_config("Missing") is None


# ============================================================================
# execute_tool
# ============================================================================


@pytest.mark.asyncio
async def test_execute_tool_delegates_to_adapter(app_config, mock_tool_adapter, sample_fault_context) -> None:
    """execute_tool() calls the adapter's execute method and returns its output."""
    registry = ToolRegistry(app_config)
    adapter = mock_tool_adapter("MockTool")
    registry._adapters["MockTool"] = adapter

    output = await registry.execute_tool("MockTool", sample_fault_context)
    assert output.tool_name == "MockTool"
    assert output.raw_text == "Result from MockTool"


@pytest.mark.asyncio
async def test_execute_tool_raises_when_tool_missing(app_config, sample_fault_context) -> None:
    """execute_tool() raises ToolNotFoundError for unknown tools."""
    registry = ToolRegistry(app_config)
    with pytest.raises(ToolNotFoundError):
        await registry.execute_tool("Missing", sample_fault_context)


# ============================================================================
# execute_parallel
# ============================================================================


@pytest.mark.asyncio
async def test_execute_parallel_runs_all_tools(app_config, mock_tool_adapter, sample_fault_context) -> None:
    """execute_parallel() returns outputs for every requested tool."""
    registry = ToolRegistry(app_config)
    registry._adapters["ToolA"] = mock_tool_adapter("ToolA")
    registry._adapters["ToolB"] = mock_tool_adapter("ToolB")

    results = await registry.execute_parallel(["ToolA", "ToolB"], sample_fault_context)

    assert set(results.keys()) == {"ToolA", "ToolB"}
    assert results["ToolA"].tool_name == "ToolA"
    assert results["ToolB"].tool_name == "ToolB"


@pytest.mark.asyncio
async def test_execute_parallel_isolates_errors(app_config, mock_tool_adapter, failing_tool_adapter, sample_fault_context) -> None:
    """execute_parallel() skips failed tools without affecting successful ones."""
    registry = ToolRegistry(app_config)
    registry._adapters["GoodTool"] = mock_tool_adapter("GoodTool")
    registry._adapters["BadTool"] = failing_tool_adapter("BadTool")

    results = await registry.execute_parallel(["GoodTool", "BadTool"], sample_fault_context)

    assert "GoodTool" in results
    assert "BadTool" in results
    assert results["BadTool"].raw_text.startswith("执行失败")
    assert results["GoodTool"].tool_name == "GoodTool"


@pytest.mark.asyncio
async def test_execute_parallel_returns_empty_for_empty_input(app_config, sample_fault_context) -> None:
    """execute_parallel() returns empty dict when given empty names list."""
    registry = ToolRegistry(app_config)
    results = await registry.execute_parallel([], sample_fault_context)
    assert results == {}


@pytest.mark.asyncio
async def test_execute_parallel_ignores_exception_results(app_config, mock_tool_adapter, sample_fault_context) -> None:
    """execute_parallel() filters out any exception objects from asyncio.gather."""
    registry = ToolRegistry(app_config)
    registry._adapters["ToolA"] = mock_tool_adapter("ToolA")

    results = await registry.execute_parallel(["ToolA"], sample_fault_context)
    assert isinstance(results["ToolA"], ToolOutput)


# ============================================================================
# load_tools — YAML loading
# ============================================================================


@pytest.mark.asyncio
async def test_load_tools_from_yaml_files(app_config, tmp_path) -> None:
    """load_tools() reads *.yaml files and registers adapters."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    yaml_content = """
tool:
  name: LightningDiagnosisTool
  display_name: Lightning
  description: Detects lightning strikes
  category: electrical
  adapter:
    type: mcp
    config:
      mcp_server: http://localhost:8000
"""
    (tools_dir / "lightning.yaml").write_text(yaml_content, encoding="utf-8")

    registry = ToolRegistry(app_config)
    await registry.load_tools()

    assert "LightningDiagnosisTool" in registry.list_tool_names()
    cfg = registry.get_tool_config("LightningDiagnosisTool")
    assert cfg is not None
    assert cfg.display_name == "Lightning"


@pytest.mark.asyncio
async def test_load_tools_skips_broken_files_and_continues(app_config, tmp_path) -> None:
    """load_tools() logs errors for broken configs but continues loading others."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    good_yaml = """
tool:
  name: GoodTool
  display_name: Good
  description: Works
  category: test
  adapter:
    type: mcp
    config: {}
"""
    (tools_dir / "good.yaml").write_text(good_yaml, encoding="utf-8")
    (tools_dir / "bad.yaml").write_text("not: valid: yaml: [", encoding="utf-8")

    registry = ToolRegistry(app_config)
    await registry.load_tools()

    assert "GoodTool" in registry.list_tool_names()


@pytest.mark.asyncio
async def test_load_tools_warns_when_directory_missing(app_config, tmp_path) -> None:
    """load_tools() returns early when the config directory does not exist."""
    app_config.tools.config_directory = str(tmp_path / "nonexistent")
    registry = ToolRegistry(app_config)
    await registry.load_tools()
    assert registry.list_tool_names() == []


# ============================================================================
# _create_adapter — custom adapter loading
# ============================================================================


def test_create_adapter_raises_on_unsupported_type(app_config) -> None:
    """_create_adapter() raises ValueError for unsupported adapter types."""
    registry = ToolRegistry(app_config)
    cfg = ToolConfig(
        name="BadTool",
        display_name="Bad",
        description="desc",
        category="cat",
        adapter=AdapterConfig(type=AdapterType.CUSTOM),
    )
    # Force an unsupported string after validation
    object.__setattr__(cfg.adapter, "type", "unsupported_type")

    with pytest.raises(ValueError) as exc_info:
        registry._create_adapter(cfg)
    assert "unsupported_type" in str(exc_info.value)


def test_load_custom_adapter_requires_module_and_class(app_config) -> None:
    """_load_custom_adapter() raises ValueError when module or class is missing."""
    registry = ToolRegistry(app_config)
    cfg = ToolConfig(
        name="CustomTool",
        display_name="Custom",
        description="desc",
        category="cat",
        adapter=AdapterConfig(type=AdapterType.CUSTOM),
    )

    with pytest.raises(ValueError) as exc_info:
        registry._load_custom_adapter(cfg)
    assert "module" in str(exc_info.value).lower()
