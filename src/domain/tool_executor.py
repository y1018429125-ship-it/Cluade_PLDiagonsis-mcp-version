"""工具执行器

根据 LLM 诊断计划并行或串行执行工具调用。
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器

    负责按照诊断计划中的工具调用列表，以并行或串行方式执行工具，
    并收集所有工具的输出结果。
    """

    def __init__(self, tool_registry: ToolRegistry):
        """初始化工具执行器

        Args:
            tool_registry: 工具注册表实例，用于查找和执行具体工具
        """
        self.tool_registry = tool_registry

    async def execute(self, plan: Dict[str, Any], context: Any) -> Dict[str, ToolOutput]:
        """按照诊断计划执行工具调用

        从计划中提取 tools_to_call 列表，根据 parallel 字段分组：
        - parallel=true 或缺失：并行执行（使用 asyncio.gather）
        - parallel=false：串行执行（按顺序逐个执行）

        对于每个工具，调用 tool_registry.execute_tool() 获取 ToolOutput。
        如果工具未找到或执行失败，捕获异常并返回包含错误信息的 ToolOutput。

        Args:
            plan: LLM 生成的诊断计划字典，包含 tools_to_call 列表
            context: 故障上下文（FaultContext 或其他上下文对象）

        Returns:
            工具名称到 ToolOutput 的映射字典
        """
        tools_to_call: List[Dict[str, Any]] = plan.get("tools_to_call", [])
        if not tools_to_call:
            logger.info("诊断计划中无工具需要调用")
            return {}

        parallel_tools: List[str] = []
        sequential_tools: List[str] = []

        for tool in tools_to_call:
            name = tool.get("name", "")
            if not name:
                logger.warning("工具调用项缺少 name 字段，跳过")
                continue
            if tool.get("parallel", True):
                parallel_tools.append(name)
            else:
                sequential_tools.append(name)

        results: Dict[str, ToolOutput] = {}

        # 并行执行
        if parallel_tools:
            logger.info(f"并行执行工具: {parallel_tools}")
            parallel_results = await asyncio.gather(
                *[self._run_tool(name, context) for name in parallel_tools],
                return_exceptions=True,
            )
            for result in parallel_results:
                if isinstance(result, Exception):
                    logger.error(f"并行工具执行异常: {result}")
                    continue
                name, output = result
                results[name] = output

        # 串行执行
        for name in sequential_tools:
            logger.info(f"串行执行工具: {name}")
            try:
                _, output = await self._run_tool(name, context)
                results[name] = output
            except Exception as e:
                logger.error(f"串行工具执行异常 {name}: {e}")
                results[name] = ToolOutput(
                    tool_name=name,
                    raw_text=f"工具未找到或执行失败: {e}",
                )

        return results

    async def _run_tool(self, name: str, context: Any) -> tuple[str, ToolOutput]:
        """执行单个工具

        Args:
            name: 工具名称
            context: 故障上下文

        Returns:
            (工具名称, ToolOutput) 元组

        Raises:
            Exception: 当工具未找到或执行失败时抛出
        """
        diag_logger = getattr(context, "diagnosis_logger", None) if context else None
        start_perf = time.perf_counter()
        try:
            output = await self.tool_registry.execute_tool(name, context)
            if diag_logger:
                diag_logger.record_tool_timing(
                    name, start_perf, time.perf_counter(), success=True
                )
            return name, output
        except Exception as e:
            logger.error(f"工具执行失败 {name}: {e}")
            if diag_logger:
                diag_logger.record_tool_timing(
                    name, start_perf, time.perf_counter(), success=False, error=str(e)
                )
            raise
