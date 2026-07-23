"""意图分类器

基于 LLM 结构化输出的意图识别。
"""

import logging
from typing import Optional

from src.core.models import DiagnosisSession, Intent, IntentType
from src.core.exceptions import IntentClassificationError
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)


class IntentClassifier:
    """意图分类器"""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def classify(
        self, message: str, session: Optional[DiagnosisSession] = None
    ) -> Intent:
        """分类用户意图"""
        try:
            session_context = self._build_session_context(session)
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(),
                },
                {
                    "role": "user",
                    "content": f"用户消息：{message}\n\n{session_context}",
                },
            ]

            intent = await self.llm.structured_output(messages, Intent)

            # 置信度检查
            if intent.confidence < 0.7:
                logger.info(f"意图置信度低 ({intent.confidence})，fallback 到 general")
                return Intent(
                    intent_type=IntentType.GENERAL,
                    confidence=1.0,
                    raw_message=message,
                )

            intent.raw_message = message
            logger.info(f"意图识别: {intent.intent_type.value} (置信度: {intent.confidence})")
            return intent

        except Exception as e:
            logger.error(f"意图分类失败: {e}")
            # fallback 到通用对话
            return Intent(
                intent_type=IntentType.GENERAL,
                confidence=1.0,
                raw_message=message,
            )

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        intent_types = [t.value for t in IntentType]
        return f"""你是输电线路故障诊断智能体的意图识别模块。

分析用户消息，判断其意图类型。可选类型：
- diagnose: 开始故障诊断（如"220kV京西线跳闸"）
- exclude_tool: 排除某个诊断工具（如"去掉雷电"、"排除覆冰"）
- include_tool: 恢复某个诊断工具（如"恢复雷电"、"加回覆冰"）
- recheck_tool: 重新检查某个工具（如"重新检查雷电"）
- adjust_weight: 调整权重（如"提高雷电权重到1.2"）
- modify_report: 修改报告（如"去掉第六章"）
- complete: 完成当前诊断（如"诊断完成"、"结束"）
- list_sessions: 查看会话列表
- switch_session: 切换会话
- save_strategy: 保存策略
- load_strategy: 加载策略
- general: 通用对话

工具名称映射规则（参数中tool_name/tool_names必须为标准名称）：
- 雷电、雷击 -> LightningDiagnosisTool
- 覆冰、结冰 -> IcingDiagnosisTool
- 风偏、大风 -> WindDiagnosisTool
- 鸟害、鸟类 -> BirdDamageDiagnosisTool
- 天气 -> WeatherDiagnosisTool

返回 JSON 格式：
{{
    "intent_type": "意图类型",
    "confidence": 0.95,
    "parameters": {{"tool_name": "标准工具名"}}  // 单工具用 tool_name
}}
或（多工具排除/恢复时）：
{{
    "intent_type": "exclude_tool",
    "confidence": 0.95,
    "parameters": {{"tool_names": ["LightningDiagnosisTool", "IcingDiagnosisTool"]}}
}}
"""

    def _build_session_context(self, session: Optional[DiagnosisSession]) -> str:
        """构建会话上下文"""
        if not session:
            return "当前无活跃会话"

        return f"""当前会话信息：
- 会话ID: {session.session_id}
- 线路: {session.line_name}
- 状态: {session.status.value}
- 已排除工具: {session.excluded_tools}
- 当前权重: {session.active_weights}
"""
