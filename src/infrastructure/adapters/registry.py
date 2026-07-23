"""Tool Adapter 注册表

动态加载和管理所有诊断工具适配器。
支持从 YAML 配置文件自动注册工具。
"""

import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.core.models import FaultContext, ToolConfig, ToolOutput
from src.core.config import AppConfig
from src.core.exceptions import ToolNotFoundError
from src.infrastructure.adapters.base import ToolAdapter
from src.infrastructure.adapters.mcp_adapter import MCPToolAdapter

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表

    管理所有诊断工具的注册、发现和执行。
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._adapters: Dict[str, ToolAdapter] = {}
        self._configs: Dict[str, ToolConfig] = {}

    async def load_tools(self) -> None:
        """从配置目录加载所有工具"""
        tools_dir = Path(self.config.tools.config_directory)
        if not tools_dir.exists():
            logger.warning(f"工具配置目录不存在: {tools_dir}")
            return

        for config_file in tools_dir.glob("*.yaml"):
            try:
                await self._load_tool_config(config_file)
            except Exception as e:
                logger.error(f"加载工具配置失败 {config_file}: {e}")

        logger.info(f"已加载 {len(self._adapters)} 个诊断工具")

    async def _load_tool_config(self, config_file: Path) -> None:
        """加载单个工具配置"""
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        tool_config = ToolConfig.model_validate(data["tool"])
        self._configs[tool_config.name] = tool_config

        # 根据适配器类型创建实例
        adapter = self._create_adapter(tool_config)
        self._adapters[tool_config.name] = adapter

        logger.info(f"注册工具: {tool_config.name} ({tool_config.display_name})")

    def _create_adapter(self, config: ToolConfig) -> ToolAdapter:
        """根据配置创建适配器实例"""
        adapter_type = config.adapter.type

        if adapter_type == "mcp":
            return MCPToolAdapter({
                **config.adapter.config,
                "tool_name": config.name,
                "display_name": config.display_name,
                "description": config.description,
                "category": config.category,
            })
        elif adapter_type == "custom":
            return self._load_custom_adapter(config)
        else:
            raise ValueError(f"不支持的适配器类型: {adapter_type}")

    def _load_custom_adapter(self, config: ToolConfig) -> ToolAdapter:
        """加载自定义适配器类"""
        module_path = config.adapter.config.get("module")
        class_name = config.adapter.config.get("class")

        if not module_path or not class_name:
            raise ValueError("自定义适配器必须指定 module 和 class")

        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        return adapter_class(config.adapter.config)

    def get_adapter(self, name: str) -> ToolAdapter:
        """获取指定工具的适配器"""
        if name not in self._adapters:
            raise ToolNotFoundError(f"工具不存在: {name}")
        return self._adapters[name]

    def list_tools(self) -> List[ToolAdapter]:
        """获取所有已注册的工具"""
        return list(self._adapters.values())

    def list_tool_names(self) -> List[str]:
        """获取所有已注册的工具名称"""
        return list(self._adapters.keys())

    def get_tool_config(self, name: str) -> Optional[ToolConfig]:
        """获取工具配置"""
        return self._configs.get(name)

    async def execute_tool(self, name: str, context: FaultContext) -> ToolOutput:
        """执行指定工具"""
        adapter = self.get_adapter(name)
        return await adapter.execute(context)

    async def execute_parallel(
        self, names: List[str], context: FaultContext
    ) -> Dict[str, ToolOutput]:
        """并行执行多个工具"""
        import asyncio

        async def run_tool(name: str) -> tuple[str, ToolOutput]:
            try:
                output = await self.execute_tool(name, context)
                return name, output
            except Exception as e:
                logger.error(f"工具执行失败 {name}: {e}")
                # 返回错误输出，不影响其他工具
                return name, ToolOutput(
                    tool_name=name,
                    raw_text=f"执行失败: {str(e)}",
                    metadata={"error": str(e)},
                )

        tasks = [run_tool(name) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            name, output = result
            outputs[name] = output

        return outputs
