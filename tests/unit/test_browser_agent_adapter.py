import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.browser_agent_adapter import BrowserAgentAdapter


class TestBrowserAgentAdapter:
    @pytest.fixture
    def adapter(self):
        config = {
            "default_city": "武汉",
            "headless": True,
            "max_steps": 5,
            "step_timeout": 30,
        }
        return BrowserAgentAdapter(config)

    def test_name_and_properties(self, adapter):
        """适配器基本属性正确"""
        assert adapter.name == "WeatherDiagnosisTool"
        assert adapter.display_name == "天气诊断"
        assert adapter.category == "environmental"

    @pytest.mark.asyncio
    async def test_execute_returns_tool_output(self, adapter):
        """execute 应返回 ToolOutput，包含天气数据"""
        context = FaultContext(line_id="L001", line_name="武汉线")

        mock_controller = MagicMock()
        mock_controller.launch = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.screenshot = AsyncMock(return_value=b"png")

        mock_loop = MagicMock()
        mock_loop.run = AsyncMock(return_value="武汉今日晴，25°C，湿度60%")

        with patch(
            "src.infrastructure.adapters.browser_agent_adapter.BrowserController",
            return_value=mock_controller,
        ), patch(
            "src.infrastructure.adapters.browser_agent_adapter.AgentLoop",
            return_value=mock_loop,
        ):
            result = await adapter.execute(context)

        assert isinstance(result, ToolOutput)
        assert result.tool_name == "WeatherDiagnosisTool"
        assert "武汉" in result.raw_text
        mock_controller.launch.assert_awaited_once()
        mock_controller.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_parses_structured_data(self, adapter):
        """execute 应解析结构化天气数据"""
        context = FaultContext(line_id="L001", line_name="武汉线")

        mock_controller = MagicMock()
        mock_controller.launch = AsyncMock()
        mock_controller.close = AsyncMock()

        mock_loop = MagicMock()
        mock_loop.run = AsyncMock(return_value="武汉今日晴，25°C，湿度60%，东风2级")

        with patch(
            "src.infrastructure.adapters.browser_agent_adapter.BrowserController",
            return_value=mock_controller,
        ), patch(
            "src.infrastructure.adapters.browser_agent_adapter.AgentLoop",
            return_value=mock_loop,
        ):
            result = await adapter.execute(context)

        assert result.structured_data is not None
        assert result.structured_data.get("city") == "武汉"
        assert result.structured_data.get("temperature") == 25
        assert result.structured_data.get("humidity") == 60
        assert result.structured_data.get("condition") == "晴"
        assert result.structured_data.get("wind_direction") == "东"
        assert result.structured_data.get("wind_level") == "2级"

    @pytest.mark.asyncio
    async def test_execute_returns_error_on_failure(self, adapter):
        """execute 在异常时应返回包含错误信息的 ToolOutput"""
        context = FaultContext(line_id="L001", line_name="武汉线")

        mock_controller = MagicMock()
        mock_controller.launch = AsyncMock(side_effect=RuntimeError("启动失败"))
        mock_controller.close = AsyncMock()

        with patch(
            "src.infrastructure.adapters.browser_agent_adapter.BrowserController",
            return_value=mock_controller,
        ):
            result = await adapter.execute(context)

        assert isinstance(result, ToolOutput)
        assert "失败" in result.raw_text
        assert result.metadata.get("error") is not None


class TestWeatherToolRegistration:
    @pytest.mark.asyncio
    async def test_weather_tool_loads(self):
        """ToolRegistry 应能加载 weather.yaml 并注册 WeatherDiagnosisTool"""
        from src.infrastructure.adapters.registry import ToolRegistry
        from src.core.config import AppConfig

        config = AppConfig()
        registry = ToolRegistry(config)
        await registry.load_tools()

        tool_names = registry.list_tool_names()
        assert "WeatherDiagnosisTool" in tool_names

        adapter = registry.get_adapter("WeatherDiagnosisTool")
        assert adapter.name == "WeatherDiagnosisTool"
        assert adapter.display_name == "天气诊断"
