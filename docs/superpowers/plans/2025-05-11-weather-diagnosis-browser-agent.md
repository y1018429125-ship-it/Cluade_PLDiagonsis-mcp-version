# 天气诊断浏览器智能体实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个基于 AI 浏览器智能体（Playwright + LLM Vision）的天气诊断工具，能够自动访问百度搜索"武汉天气"并提取结构化天气数据。

**Architecture:** 浏览器智能体由 BrowserController（生命周期）、ActionExecutor（动作执行）、AgentLoop（LLM 决策循环）三层组成，通过 BrowserAgentAdapter 接入现有 ToolAdapter 体系，weather.yaml 注册到 ToolRegistry。

**Tech Stack:** Python 3.12, Playwright, OpenAI-compatible LLM API (gemma-4-31B-it), pytest, Pydantic v2

---

## 文件清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/infrastructure/adapters/browser/controller.py` | Playwright 浏览器生命周期管理（启动、截图、关闭） |
| `src/infrastructure/adapters/browser/action_executor.py` | 将 LLM 决策解析为 Playwright 操作（点击、输入、导航等） |
| `src/infrastructure/adapters/browser/agent_loop.py` | LLM 决策主循环（截图→分析→决策→执行） |
| `src/infrastructure/adapters/browser/__init__.py` | browser 包暴露 |
| `src/infrastructure/adapters/browser_agent_adapter.py` | 继承 ToolAdapter，组装 controller + agent_loop + action_executor |
| `config/tools/weather.yaml` | 天气工具配置，注册到 ToolRegistry |
| `tests/unit/test_browser_controller.py` | BrowserController 单元测试 |
| `tests/unit/test_action_executor.py` | ActionExecutor 单元测试 |
| `tests/unit/test_agent_loop.py` | AgentLoop 单元测试 |
| `tests/unit/test_browser_agent_adapter.py` | BrowserAgentAdapter 集成测试 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `pyproject.toml` | 添加 `playwright>=1.40.0` 到 dependencies |

---

## 依赖检查

项目当前依赖中没有 Playwright：
- `pyproject.toml` dependencies 列表需追加 `playwright>=1.40.0`
- 安装后需执行 `playwright install chromium` 下载浏览器

---

## Task 1: 添加 Playwright 依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在 pyproject.toml 添加 playwright**

```toml
dependencies = [
    "flask>=2.3.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
    "python-docx>=0.8.11",
    "httpx>=0.24.0",
    "openai>=1.0.0",
    "playwright>=1.40.0",
]
```

- [ ] **Step 2: 安装依赖**

Run: `cd /mnt/e/Cluade_PLDiagonsis && pip install playwright>=1.40.0`
Expected: 安装成功

- [ ] **Step 3: 安装 Chromium 浏览器**

Run: `playwright install chromium`
Expected: Chromium 下载完成

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add playwright for browser automation"
```

---

## Task 2: 实现 BrowserController

**Files:**
- Create: `src/infrastructure/adapters/browser/controller.py`
- Create: `src/infrastructure/adapters/browser/__init__.py`
- Test: `tests/unit/test_browser_controller.py`

`BrowserController` 负责 Playwright 浏览器的生命周期：启动 headless Chromium、创建页面、截图、关闭。

- [ ] **Step 1: 写测试 — BrowserController.launch 启动浏览器**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.adapters.browser.controller import BrowserController


class TestBrowserController:
    @pytest.fixture
    def controller(self):
        return BrowserController(headless=True)

    @pytest.mark.asyncio
    async def test_launch_starts_browser(self):
        """launch() 应启动 browser 和 context"""
        ctrl = BrowserController(headless=True)
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch("playwright.async_api.async_playwright", return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_playwright),
            __aexit__=AsyncMock(return_value=False),
        )):
            await ctrl.launch()

        assert ctrl.browser is mock_browser
        assert ctrl.context is mock_context
        assert ctrl.page is mock_page
        mock_playwright.chromium.launch.assert_awaited_once_with(headless=True)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /mnt/e/Cluade_PLDiagonsis && pytest tests/unit/test_browser_controller.py::TestBrowserController::test_launch_starts_browser -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.infrastructure.adapters.browser.controller'`

- [ ] **Step 3: 实现 BrowserController**

```python
"""Playwright 浏览器生命周期管理器"""

import logging
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


class BrowserController:
    """管理 Playwright 浏览器的启动、页面创建、截图和关闭。"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def launch(self) -> None:
        """启动 headless Chromium 浏览器。"""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        self.page = await self.context.new_page()
        logger.info("浏览器启动完成")

    async def screenshot(self) -> bytes:
        """截取当前页面全屏截图，返回 PNG 字节。"""
        if self.page is None:
            raise RuntimeError("浏览器未启动，请先调用 launch()")
        return await self.page.screenshot(full_page=True, type="png")

    async def close(self) -> None:
        """关闭浏览器并释放资源。"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self._playwright = None
        logger.info("浏览器已关闭")

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
```

- [ ] **Step 4: 创建 browser 包 `__init__.py`**

```python
"""浏览器智能体子包"""

from src.infrastructure.adapters.browser.controller import BrowserController
from src.infrastructure.adapters.browser.action_executor import ActionExecutor
from src.infrastructure.adapters.browser.agent_loop import AgentLoop

__all__ = ["BrowserController", "ActionExecutor", "AgentLoop"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/test_browser_controller.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/adapters/browser/ tests/unit/test_browser_controller.py
git commit -m "feat: add BrowserController for playwright lifecycle"
```

---

## Task 3: 实现 ActionExecutor

**Files:**
- Create: `src/infrastructure/adapters/browser/action_executor.py`
- Test: `tests/unit/test_action_executor.py`

`ActionExecutor` 将 LLM 返回的决策 JSON 转换为 Playwright 实际操作。支持的动作：`navigate`, `click`, `type`, `scroll`, `wait`, `finish`。

元素定位策略（分层容错）：
1. 语义匹配：注入 JS 标记可交互元素（`data-agent-id`），通过 placeholder/aria-label/text 文本相似度匹配
2. 如未匹配到，抛出异常由 AgentLoop 处理

- [ ] **Step 1: 写测试 — ActionExecutor.execute_navigate**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.adapters.browser.action_executor import ActionExecutor, AgentAction


class TestActionExecutor:
    @pytest.fixture
    def mock_page(self):
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        return page

    @pytest.fixture
    def executor(self, mock_page):
        return ActionExecutor(mock_page)

    @pytest.mark.asyncio
    async def test_execute_navigate(self, executor, mock_page):
        """navigate 动作应调用 page.goto"""
        action = AgentAction(action="navigate", value="https://www.baidu.com")
        await executor.execute(action)
        mock_page.goto.assert_awaited_once_with("https://www.baidu.com", wait_until="domcontentloaded")
```

- [ ] **Step 2: 写测试 — ActionExecutor.execute_type**

```python
    @pytest.mark.asyncio
    async def test_execute_type_with_semantic_match(self, executor, mock_page):
        """type 动作应通过语义匹配找到输入框并填入内容"""
        # 模拟页面上的可交互元素
        mock_element = MagicMock()
        mock_element.input_value = AsyncMock(return_value="")
        mock_element.fill = AsyncMock()

        # 模拟 evaluate 返回标记后的元素列表
        mock_page.evaluate = AsyncMock(return_value=[
            {"agent_id": 1, "tag": "input", "type": "text", "placeholder": "搜索", "aria_label": "", "text": ""}
        ])
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        action = AgentAction(action="type", target="搜索框", value="武汉天气")
        await executor.execute(action)

        mock_element.fill.assert_awaited_once_with("武汉天气")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/unit/test_action_executor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: 实现 ActionExecutor**

```python
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
    INTERACTIVE_SELECTOR = "button, input, a, select, textarea, [role='button']"

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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/test_action_executor.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/adapters/browser/action_executor.py tests/unit/test_action_executor.py
git commit -m "feat: add ActionExecutor for LLM decision-to-playwright mapping"
```

---

## Task 4: 实现 AgentLoop

**Files:**
- Create: `src/infrastructure/adapters/browser/agent_loop.py`
- Test: `tests/unit/test_agent_loop.py`

`AgentLoop` 是浏览器智能体的决策主循环：截图 → LLM 分析 → 解析决策 → 执行 → 记录历史，直到 `action="finish"`、达到 `max_steps`、或发生不可恢复错误。

- [ ] **Step 1: 写测试 — AgentLoop.run completes on finish action**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.adapters.browser.agent_loop import AgentLoop
from src.infrastructure.adapters.browser.action_executor import AgentAction


class TestAgentLoop:
    @pytest.fixture
    def mock_llm_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_controller(self):
        ctrl = MagicMock()
        ctrl.screenshot = AsyncMock(return_value=b"fake_png_bytes")
        return ctrl

    @pytest.fixture
    def mock_executor(self):
        exec_ = MagicMock()
        exec_.execute = AsyncMock()
        return exec_

    @pytest.mark.asyncio
    async def test_run_completes_when_finish_action(self, mock_llm_service, mock_controller, mock_executor):
        """当 LLM 返回 finish 动作时，run 应立即返回 answer"""
        mock_llm_service.chat = AsyncMock(return_value='{"thought":"完成","action":"finish","answer":"武汉晴 25°C"}')

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
        )

        result = await loop.run("查询武汉天气")
        assert result == "武汉晴 25°C"
        mock_executor.execute.assert_not_called()  # finish 不需要执行器动作
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_agent_loop.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 AgentLoop**

```python
"""浏览器智能体决策主循环"""

import base64
import json
import logging
from typing import List, Optional

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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_agent_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/adapters/browser/agent_loop.py tests/unit/test_agent_loop.py
git commit -m "feat: add AgentLoop for LLM-driven browser automation"
```

---

## Task 5: 实现 BrowserAgentAdapter

**Files:**
- Create: `src/infrastructure/adapters/browser_agent_adapter.py`
- Test: `tests/unit/test_browser_agent_adapter.py`

`BrowserAgentAdapter` 继承 `ToolAdapter`，组装 BrowserController + AgentLoop + ActionExecutor。`execute()` 方法被诊断引擎调用，返回 `ToolOutput`。

demo 阶段查询城市固定为"武汉"，参数提取功能预留扩展点。

- [ ] **Step 1: 写测试 — BrowserAgentAdapter.execute returns ToolOutput**

```python
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

        # Mock 内部组件
        mock_controller = MagicMock()
        mock_controller.launch = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.screenshot = AsyncMock(return_value=b"png")

        mock_loop = MagicMock()
        mock_loop.run = AsyncMock(return_value="武汉今日晴，25°C，湿度60%")

        with patch("src.infrastructure.adapters.browser_agent_adapter.BrowserController", return_value=mock_controller), \
             patch("src.infrastructure.adapters.browser_agent_adapter.AgentLoop", return_value=mock_loop):

            result = await adapter.execute(context)

        assert isinstance(result, ToolOutput)
        assert result.tool_name == "WeatherDiagnosisTool"
        assert "武汉" in result.raw_text
        mock_controller.launch.assert_awaited_once()
        mock_controller.close.assert_awaited_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_browser_agent_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 BrowserAgentAdapter**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_browser_agent_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/adapters/browser_agent_adapter.py tests/unit/test_browser_agent_adapter.py
git commit -m "feat: add BrowserAgentAdapter for weather diagnosis"
```

---

## Task 6: 创建 weather.yaml 配置

**Files:**
- Create: `config/tools/weather.yaml`

将天气工具注册到 ToolRegistry。适配器类型为 `custom`，指定 module 和 class。

- [ ] **Step 1: 编写 weather.yaml**

```yaml
tool:
  name: "WeatherDiagnosisTool"
  display_name: "天气诊断"
  description: "通过浏览器访问百度查询指定城市天气状况，包括温度、湿度、天气状况、风向风力等"
  category: "environmental"
  adapter:
    type: "custom"
    config:
      module: "src.infrastructure.adapters.browser_agent_adapter"
      class: "BrowserAgentAdapter"
      # demo 阶段固定查询城市
      default_city: "武汉"
      # 浏览器配置
      headless: true
      max_steps: 10
      step_timeout: 30
  output_schema:
    type: "structured"
    fields:
      - name: "city"
        type: "string"
        description: "城市名"
      - name: "temperature"
        type: "float"
        description: "温度(°C)"
      - name: "humidity"
        type: "float"
        description: "湿度(%)"
      - name: "condition"
        type: "string"
        description: "天气状况"
      - name: "wind_direction"
        type: "string"
        description: "风向"
      - name: "wind_level"
        type: "string"
        description: "风力等级"
  report_mapping:
    chapter: "诊断证据"
    render_template: "table"
```

- [ ] **Step 2: 验证 YAML 格式正确**

Run: `cd /mnt/e/Cluade_PLDiagonsis && python -c "import yaml; yaml.safe_load(open('config/tools/weather.yaml'))"`
Expected: 无报错，正常退出

- [ ] **Step 3: Commit**

```bash
git add config/tools/weather.yaml
git commit -m "config: add weather tool registration"
```

---

## Task 7: 验证工具注册

**Files:**
- 无文件修改，仅验证

确保 weather.yaml 能被 ToolRegistry 正确加载。

- [ ] **Step 1: 写快速验证测试**

```python
import pytest
from src.infrastructure.adapters.registry import ToolRegistry
from src.core.config import AppConfig


class TestWeatherToolRegistration:
    @pytest.mark.asyncio
    async def test_weather_tool_loads(self):
        """ToolRegistry 应能加载 weather.yaml 并注册 WeatherDiagnosisTool"""
        config = AppConfig()
        registry = ToolRegistry(config)
        await registry.load_tools()

        tool_names = registry.list_tool_names()
        assert "WeatherDiagnosisTool" in tool_names

        adapter = registry.get_adapter("WeatherDiagnosisTool")
        assert adapter.name == "WeatherDiagnosisTool"
        assert adapter.display_name == "天气诊断"
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/unit/test_browser_agent_adapter.py::TestWeatherToolRegistration -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "test: verify weather tool registration in registry"
```

---

## Task 8: 全量测试回归

**Files:**
- 无文件修改

确保新增代码没有破坏现有 288 个测试。

- [ ] **Step 1: 运行全量测试**

Run: `cd /mnt/e/Cluade_PLDiagonsis && pytest tests/unit/ -q`
Expected: 全部通过（原有 288 + 新增若干）

- [ ] **Step 2: 如有失败，修复后再提交**

---

## Task 9: 前端工具列表更新（自动生效）

**Files:**
- 无需修改前端代码

天气工具通过 `/api/tools` 自动暴露给前端。前端 `ToolList.vue` 和 `StrategyManager.vue` 会动态获取工具列表，无需硬编码修改。

验证：启动后端后访问 `/api/tools`，响应中应包含 WeatherDiagnosisTool。

---

## 手动验证步骤（完成后执行）

1. 启动后端服务：`python -m src.main`（或项目启动方式）
2. 访问 `GET /api/tools`，确认返回包含 WeatherDiagnosisTool
3. 通过聊天接口发送 "220kV武汉线跳闸"，观察诊断流程中是否触发天气诊断
4. 检查日志输出，确认浏览器启动、百度搜索、结果提取的流程

---

## Spec 覆盖率检查

| 设计文档章节 | 实现任务 | 状态 |
|-------------|---------|------|
| 3.1 BrowserController | Task 2 | 已覆盖 |
| 3.2 AgentLoop | Task 4 | 已覆盖 |
| 3.3 ActionExecutor | Task 3 | 已覆盖 |
| BrowserAgentAdapter | Task 5 | 已覆盖 |
| weather.yaml | Task 6 | 已覆盖 |
| 错误处理（6） | 各组件 try/except | 已覆盖 |
| 安全机制（6.1） | BrowserController headless/timeout | 已覆盖 |
| 输出格式（5.2） | BrowserAgentAdapter._parse_weather_data | 已覆盖 |
| 测试策略（8） | Task 2-7 的测试文件 | 已覆盖 |
