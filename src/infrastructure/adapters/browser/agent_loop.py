"""浏览器智能体决策主循环"""

import base64
import json
import logging
from typing import List

from src.infrastructure.adapters.browser.controller import BrowserController
from src.infrastructure.adapters.browser.action_executor import ActionExecutor, AgentAction
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)


class AgentLoop:
    """LLM 驱动的浏览器自动化决策循环。"""

    def __init__(
        self,
        llm_service: LLMService,
        controller: BrowserController,
        executor: ActionExecutor,
        max_steps: int = 10,
        step_timeout: float = 30.0,
    ):
        self.llm_service = llm_service
        self.controller = controller
        self.executor = executor
        self.max_steps = max_steps
        self.step_timeout = step_timeout

    async def run(self, task: str) -> str:
        """执行浏览器任务，返回最终结果文本。

        循环直到：
        - LLM 返回 action="finish"
        - 达到 max_steps 限制
        - 发生不可恢复错误
        """
        action_history: List[str] = []

        for step in range(1, self.max_steps + 1):
            logger.info(f"--- Step {step}/{self.max_steps} ---")

            try:
                # 1. 截图
                screenshot_bytes = await self.controller.screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                # 2. 构建 prompt
                prompt = self._build_prompt(task, action_history, screenshot_b64)

                # 3. 调用 LLM
                messages = [{"role": "user", "content": prompt}]
                response_text = await self.llm_service.chat(messages, temperature=0.3, max_tokens=2048)

                # 4. 解析决策
                action = self._parse_action(response_text)
                logger.info(f"LLM 决策: {action.action} target={action.target} value={action.value}")

                # 5. 记录历史
                history_entry = f"Step {step}: {action.action}"
                if action.target:
                    history_entry += f" target='{action.target}'"
                if action.value:
                    history_entry += f" value='{action.value}'"
                action_history.append(history_entry)

                # 6. 执行动作（finish 除外）
                if action.action == "finish":
                    return action.answer or "任务完成，无返回值"

                await self.executor.execute(action)

            except Exception as e:
                logger.error(f"Step {step} 失败: {e}")
                action_history.append(f"Step {step}: 错误 - {e}")
                # 简单重试策略：如果是元素定位失败，等待后重试一次
                if "无法定位元素" in str(e) and step < self.max_steps:
                    logger.info("等待 2 秒后重试...")
                    import asyncio
                    await asyncio.sleep(2)
                    continue
                raise

        # 达到 max_steps
        logger.warning(f"达到最大步数 {self.max_steps}，任务未完成")
        return f"任务未在 {self.max_steps} 步内完成。历史动作:\n" + "\n".join(action_history)

    def _build_prompt(self, task: str, action_history: List[str], screenshot_b64: str) -> str:
        """构建发送给 LLM 的决策 prompt。"""
        history_text = "\n".join(action_history) if action_history else "（无）"

        prompt = f"""你是浏览器自动化助手。当前任务：{task}

[历史动作]
{history_text}

[当前页面截图]
<img src="data:image/png;base64,{screenshot_b64}" />

请分析当前页面，决定下一步动作。

可交互元素包括：按钮、输入框、链接、下拉框等。请用自然语言描述目标元素（如"搜索框"、"百度一下按钮"）。

返回 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "thought": "对当前页面的分析...",
  "action": "navigate|click|type|scroll|wait|finish",
  "target": "元素描述或null",
  "value": "输入值或URL或null",
  "answer": "任务完成时的答案或null"
}}

约束：
- action 必须是上述允许值之一
- target 使用自然语言描述元素
- answer 仅在 action="finish" 时有效
- 如果任务已完成，action 设为 "finish" 并在 answer 中给出结果
"""
        return prompt

    def _parse_action(self, response_text: str) -> AgentAction:
        """解析 LLM 返回的 JSON 决策。"""
        # 清理可能的 markdown 代码块
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 返回非 JSON: {e}\n内容: {response_text[:200]}")

        return AgentAction.model_validate(data)
