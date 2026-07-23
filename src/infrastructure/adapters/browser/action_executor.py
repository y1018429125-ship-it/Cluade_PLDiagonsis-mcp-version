"""动作执行器 —— 将 LLM 决策转换为 Playwright 操作"""

import asyncio
import difflib
import logging
from typing import Optional

from playwright.async_api import Page
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentAction(BaseModel):
    """LLM 返回的单个动作决策"""
    thought: str = ""
    action: str = Field(..., pattern="^(navigate|click|type|scroll|wait|finish)$")
    target: Optional[str] = None
    value: Optional[str] = None
    answer: Optional[str] = None


class ActionExecutor:
    """执行 LLM 决策的 Playwright 操作。"""

    # 用于语义匹配的可交互元素选择器
    INTERACTIVE_SELECTOR = 'button, input, a, select, textarea, [role="button"]'

    def __init__(self, page: Page):
        self.page = page

    async def execute(self, action: AgentAction) -> None:
        """根据 AgentAction 执行对应的 Playwright 操作。"""
        handler = getattr(self, f"_handle_{action.action}", None)
        if handler is None:
            raise ValueError(f"不支持的动作类型: {action.action}")
        await handler(action)

    async def _handle_navigate(self, action: AgentAction) -> None:
        """导航到指定 URL。"""
        url = action.value or "about:blank"
        logger.info(f"[navigate] {url}")
        await self.page.goto(url, wait_until="domcontentloaded")

    async def _handle_click(self, action: AgentAction) -> None:
        """点击页面元素。"""
        target = action.target or ""
        logger.info(f"[click] {target}")
        element = await self._find_element(target)
        await element.click()

    async def _handle_type(self, action: AgentAction) -> None:
        """在输入框填入内容。"""
        target = action.target or ""
        value = action.value or ""
        logger.info(f"[type] {target} => {value}")
        element = await self._find_element(target)
        await element.fill(value)

    async def _handle_scroll(self, action: AgentAction) -> None:
        """滚动页面。"""
        direction = action.value or "down"
        logger.info(f"[scroll] {direction}")
        if direction == "down":
            await self.page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
        elif direction == "up":
            await self.page.evaluate("window.scrollBy(0, -window.innerHeight / 2)")

    async def _handle_wait(self, action: AgentAction) -> None:
        """等待页面稳定。"""
        logger.info("[wait] 等待页面加载...")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # 网络 already idle 或超时都继续
        await asyncio.sleep(0.5)

    async def _handle_finish(self, action: AgentAction) -> None:
        """任务完成，无需操作。"""
        logger.info(f"[finish] {action.answer}")

    async def _find_element(self, target_description: str):
        """通过语义描述查找页面元素。

        策略：
        1. 注入 data-agent-id 标记所有可交互元素
        2. 收集每个元素的描述文本（placeholder/aria-label/text）
        3. 用 difflib 相似度匹配 target_description
        4. 返回最匹配的元素
        """
        # 注入标记
        script = """
        () => {
            const elements = document.querySelectorAll('%s');
            const results = [];
            elements.forEach((el, idx) => {
                const id = idx + 1;
                el.setAttribute('data-agent-id', id);
                const desc = [
                    el.placeholder || '',
                    el.getAttribute('aria-label') || '',
                    el.textContent?.trim()?.substring(0, 50) || '',
                    el.getAttribute('title') || '',
                    el.name || ''
                ].filter(Boolean).join(' | ');
                results.push({
                    agent_id: id,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    description: desc
                });
            });
            return results;
        }
        """ % self.INTERACTIVE_SELECTOR

        elements = await self.page.evaluate(script)

        if not elements:
            raise RuntimeError(f"页面上未找到可交互元素，无法定位: {target_description}")

        # 相似度匹配
        best_match = None
        best_score = 0.0
        for el in elements:
            desc = el.get("description", "")
            score = difflib.SequenceMatcher(None, target_description.lower(), desc.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = el

        # 阈值：至少 0.3 的相似度
        if best_match and best_score >= 0.3:
            agent_id = best_match["agent_id"]
            logger.info(f"语义匹配: '{target_description}' -> agent_id={agent_id} (score={best_score:.2f})")
            element = await self.page.query_selector(f'[data-agent-id="{agent_id}"]')
            if element:
                return element

        raise RuntimeError(
            f"无法定位元素: '{target_description}'，最佳匹配: {best_match} (score={best_score:.2f})"
        )
