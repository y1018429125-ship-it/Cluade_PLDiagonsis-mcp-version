"""LLM 服务封装

提供统一的 LLM 调用接口，支持结构化输出和流式输出。
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.core.config import LLMConfig
from src.core.exceptions import LLMServiceError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """LLM 服务"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """普通对话"""
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise LLMServiceError(f"LLM 调用失败: {str(e)}")

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式对话，逐字返回 LLM 输出"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            raise LLMServiceError(f"LLM 流式调用失败: {str(e)}")

    async def structured_output(
        self, messages: list[dict], output_schema: Type[T], **kwargs
    ) -> T:
        """结构化输出

        使用 OpenAI JSON mode 或 function calling 获取结构化响应。
        """
        try:
            # 构建 schema 描述
            schema_desc = output_schema.model_json_schema()

            system_msg = {
                "role": "system",
                "content": (
                    f"你必须以 JSON 格式响应，严格遵循以下 schema:\n"
                    f"{json.dumps(schema_desc, ensure_ascii=False, indent=2)}\n"
                    f"只输出 JSON，不要包含其他内容。"
                ),
            }

            all_messages = [system_msg] + messages

            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=all_messages,
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            return output_schema.model_validate(data)

        except json.JSONDecodeError as e:
            logger.error(f"LLM 返回非 JSON: {e}")
            raise LLMServiceError(f"LLM 返回格式错误: {str(e)}")
        except Exception as e:
            logger.error(f"LLM 结构化输出失败: {e}")
            raise LLMServiceError(f"LLM 结构化输出失败: {str(e)}")

    async def intent_classification(
        self, message: str, session_context: Optional[dict] = None
    ) -> dict:
        """意图识别专用接口"""
        from src.core.models import IntentType

        intent_types = [t.value for t in IntentType]

        prompt = f"""分析用户消息，判断意图类型。

可选意图类型：{', '.join(intent_types)}

用户消息：{message}

当前会话状态：{session_context or '无活跃会话'}

请返回 JSON 格式：
{{
    "intent_type": "意图类型",
    "confidence": 0.95,
    "parameters": {{
        "key": "value"
    }}
}}
"""

        messages = [{"role": "user", "content": prompt}]
        from src.core.models import Intent
        return await self.structured_output(messages, Intent)
