"""天气诊断浏览器智能体适配器

通过 AI 浏览器智能体访问百度搜索天气信息。
"""

import logging
from typing import Any, Dict

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.base import ToolAdapter
from src.infrastructure.adapters.browser.controller import BrowserController
from src.infrastructure.adapters.browser.agent_loop import AgentLoop
from src.infrastructure.adapters.browser.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class BrowserAgentAdapter(ToolAdapter):
    """浏览器智能体适配器 —— 使用 Playwright + LLM 自动浏览网页获取天气数据。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.default_city = config.get("default_city", "武汉")
        self.headless = config.get("headless", True)
        self.max_steps = config.get("max_steps", 10)
        self.step_timeout = config.get("step_timeout", 30)

    @property
    def name(self) -> str:
        return "WeatherDiagnosisTool"

    @property
    def display_name(self) -> str:
        return "天气诊断"

    @property
    def description(self) -> str:
        return "通过浏览器访问百度查询指定城市天气状况，包括温度、湿度、天气状况、风向风力等"

    @property
    def category(self) -> str:
        return "environmental"

    async def execute(self, context: FaultContext) -> ToolOutput:
        """执行天气诊断。

        demo 阶段固定查询城市为"武汉"。未来扩展点：从 line_name 提取城市名。
        """
        city = self._extract_city(context)
        logger.info(f"开始天气诊断: city={city}")

        controller = BrowserController(headless=self.headless)
        try:
            await controller.launch()

            # 创建 executor 和 agent loop
            executor = ActionExecutor(controller.page)
            # LLMService 从 container 获取（外部注入或延迟加载）
            llm_service = self._get_llm_service()

            agent_loop = AgentLoop(
                llm_service=llm_service,
                controller=controller,
                executor=executor,
                max_steps=self.max_steps,
                step_timeout=self.step_timeout,
            )

            task = f"访问百度，搜索'{city}天气'，获取当前天气状况（温度、湿度、天气、风向风力），以文字返回结果。"
            answer = await agent_loop.run(task)

            # 解析结构化数据
            structured = self._parse_weather_data(answer, city)

            return ToolOutput(
                tool_name=self.name,
                raw_text=answer,
                structured_data=structured,
                metadata={
                    "source": "baidu",
                    "city": city,
                    "query_method": "browser_agent",
                },
            )

        except Exception as e:
            logger.error(f"天气诊断失败: {e}")
            return ToolOutput(
                tool_name=self.name,
                raw_text=f"天气诊断失败: {str(e)}",
                metadata={"error": str(e), "city": city},
            )
        finally:
            await controller.close()

    def _extract_city(self, context: FaultContext) -> str:
        """从故障上下文中提取城市名。

        demo 阶段固定返回武汉。预留扩展点：解析 line_name 提取城市。
        """
        # TODO: 未来从 line_name 中提取城市名，如 "武汉线" -> "武汉"
        return self.default_city

    def _get_llm_service(self):
        """获取 LLMService 实例。"""
        # 通过容器获取单例，避免循环导入
        from src.interfaces.dependency_injection import get_container
        container = get_container()
        return container.llm_service

    def _parse_weather_data(self, raw_text: str, city: str) -> Dict[str, Any]:
        """从 LLM 返回的文本中解析结构化天气数据。

        demo 阶段使用简单正则/关键词匹配。未来可调用 LLM 做结构化提取。
        """
        import re

        data: Dict[str, Any] = {"city": city}

        # 温度：匹配 25°C 或 25℃ 或 25度
        temp_match = re.search(r'(\d+)[°℃度]', raw_text)
        if temp_match:
            data["temperature"] = int(temp_match.group(1))

        # 湿度：匹配 60% 或 湿度60
        humidity_match = re.search(r'(\d+)%', raw_text)
        if humidity_match:
            data["humidity"] = int(humidity_match.group(1))

        # 天气状况：晴、阴、多云、雨、雪等
        conditions = ["晴", "阴", "多云", "雨", "雪", "雾", "霾", "雷阵雨", "小雨", "大雨"]
        for cond in conditions:
            if cond in raw_text:
                data["condition"] = cond
                break

        # 风向：东、南、西、北、东南、东北、西南、西北
        wind_dir_match = re.search(r'(东|南|西|北|东南|东北|西南|西北)风?', raw_text)
        if wind_dir_match:
            data["wind_direction"] = wind_dir_match.group(1)

        # 风力：1-12级
        wind_level_match = re.search(r'(\d+)[级]', raw_text)
        if wind_level_match:
            data["wind_level"] = f"{wind_level_match.group(1)}级"

        return data
