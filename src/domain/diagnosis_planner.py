"""诊断计划器

通过调用 LLM 生成 JSON 格式的诊断计划，决定需要调用哪些工具以及报告结构。
支持流式输出思考过程。
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_PLAN: Dict[str, Any] = {
    "reasoning": "Fallback: call all available tools",
    "tools_to_call": [],
    "report_structure": ["概述", "故障分析", "诊断证据", "诊断结论", "处理建议"],
}


class DiagnosisPlanner:
    """诊断计划器

    使用 LLM 根据用户输入生成诊断计划，包括需要调用的工具列表和报告结构。
    """

    def __init__(self, llm_service: LLMService):
        """初始化诊断计划器

        Args:
            llm_service: LLM 服务实例，用于生成诊断计划
        """
        self.llm = llm_service

    async def plan(
        self,
        prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """生成诊断计划

        调用 LLM 获取 JSON 格式的诊断计划，包含 reasoning、tools_to_call 和 report_structure。
        如果提供了 on_chunk 回调，则以流式方式输出思考过程。
        如果 LLM 返回无法解析的内容，则返回默认计划。

        Args:
            prompt: 用户输入的诊断提示
            on_chunk: 可选的回调函数，接收每个文本片段

        Returns:
            解析后的诊断计划字典
        """
        messages = [
            {
                "role": "system",
                "content": "你是一个诊断计划专家。只输出 JSON，不要任何解释。",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            if on_chunk is not None:
                response = await self._stream_plan(messages, on_chunk)
            else:
                response = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"LLM 调用失败，使用默认计划: {e}")
            return DEFAULT_PLAN.copy()

        parsed = self._parse_json(response)
        if parsed is None:
            logger.warning("LLM 返回内容无法解析为 JSON，使用默认计划")
            return DEFAULT_PLAN.copy()

        return self._validate_plan(parsed)

    async def _stream_plan(
        self,
        messages: list[dict],
        on_chunk: Callable[[str], None],
    ) -> str:
        """流式生成诊断计划，逐块回调"""
        full_text = ""
        async for chunk in self.llm.stream_chat(messages):
            full_text += chunk
            on_chunk(chunk)
        return full_text

    def _parse_json(self, response: str) -> Dict[str, Any] | None:
        """从 LLM 响应中解析 JSON

        依次尝试以下策略：
        1. 使用正则表达式提取 JSON 代码块
        2. 尝试将整个响应作为 JSON 解析

        Args:
            response: LLM 返回的原始文本

        Returns:
            解析后的字典，若解析失败则返回 None
        """
        # 策略 1: 正则提取 JSON 块
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.debug("正则提取的 JSON 块解析失败，尝试完整响应解析")

        # 策略 2: 尝试完整响应作为 JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"无法将 LLM 响应解析为 JSON: {response[:200]}")
            return None

    def _validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """验证并补全诊断计划

        确保 plan 包含必需的 tools_to_call 键，若缺少 report_structure 则添加默认值。

        Args:
            plan: 从 LLM 响应解析出的原始计划字典

        Returns:
            验证并补全后的计划字典
        """
        if "tools_to_call" not in plan:
            logger.warning("LLM 返回的计划缺少 tools_to_call 字段，使用默认计划")
            return DEFAULT_PLAN.copy()

        if "report_structure" not in plan:
            logger.info("LLM 返回的计划缺少 report_structure 字段，添加默认值")
            plan["report_structure"] = DEFAULT_PLAN["report_structure"].copy()

        return plan
