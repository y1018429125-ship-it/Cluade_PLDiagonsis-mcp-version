import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.adapters.browser.action_executor import ActionExecutor, AgentAction


class TestActionExecutor:
    @pytest.fixture
    def mock_page(self):
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector = AsyncMock()
        return page

    @pytest.fixture
    def executor(self, mock_page):
        return ActionExecutor(mock_page)

    @pytest.mark.asyncio
    async def test_execute_navigate(self, executor, mock_page):
        """navigate 动作应调用 page.goto"""
        action = AgentAction(action="navigate", value="https://www.baidu.com")
        await executor.execute(action)
        mock_page.goto.assert_awaited_once_with(
            "https://www.baidu.com", wait_until="domcontentloaded"
        )

    @pytest.mark.asyncio
    async def test_execute_click_with_semantic_match(self, executor, mock_page):
        """click 动作应通过语义匹配找到元素并点击"""
        mock_element = MagicMock()
        mock_element.click = AsyncMock()

        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "agent_id": 1,
                    "tag": "button",
                    "type": "",
                    "description": "百度一下",
                }
            ]
        )
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        action = AgentAction(action="click", target="百度一下按钮")
        await executor.execute(action)

        mock_element.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_type_with_semantic_match(self, executor, mock_page):
        """type 动作应通过语义匹配找到输入框并填入内容"""
        mock_element = MagicMock()
        mock_element.fill = AsyncMock()

        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "agent_id": 1,
                    "tag": "input",
                    "type": "text",
                    "description": "搜索",
                }
            ]
        )
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        action = AgentAction(action="type", target="搜索框", value="武汉天气")
        await executor.execute(action)

        mock_element.fill.assert_awaited_once_with("武汉天气")

    @pytest.mark.asyncio
    async def test_execute_scroll_down(self, executor, mock_page):
        """scroll down 应执行向下滚动"""
        action = AgentAction(action="scroll", value="down")
        await executor.execute(action)
        mock_page.evaluate.assert_awaited_once()
        assert "scrollBy" in mock_page.evaluate.call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_wait(self, executor, mock_page):
        """wait 动作应等待页面加载"""
        action = AgentAction(action="wait")
        await executor.execute(action)
        mock_page.wait_for_load_state.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_finish(self, executor, mock_page):
        """finish 动作不应调用 page 任何方法"""
        action = AgentAction(action="finish", answer="完成")
        await executor.execute(action)
        # finish 不调用任何 page 方法
        mock_page.goto.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_semantic_match_no_elements_raises(self, executor, mock_page):
        """页面上无可交互元素时应抛出 RuntimeError"""
        mock_page.evaluate = AsyncMock(return_value=[])

        action = AgentAction(action="click", target="不存在的按钮")
        with pytest.raises(RuntimeError, match="未找到可交互元素"):
            await executor.execute(action)

    @pytest.mark.asyncio
    async def test_semantic_match_low_score_raises(self, executor, mock_page):
        """相似度低于阈值时应抛出 RuntimeError"""
        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "agent_id": 1,
                    "tag": "div",
                    "type": "",
                    "description": "完全不相关",
                }
            ]
        )
        mock_page.query_selector = AsyncMock(return_value=None)

        action = AgentAction(action="click", target="abcxyz123")
        with pytest.raises(RuntimeError, match="无法定位元素"):
            await executor.execute(action)

    @pytest.mark.asyncio
    async def test_unsupported_action_raises(self, executor):
        """不支持的动作类型应抛出 ValueError"""
        # 构造一个无效 action 来绕过 AgentAction 的校验
        action = AgentAction(action="navigate")
        action.action = "invalid_action"
        with pytest.raises(ValueError, match="不支持的动作类型"):
            await executor.execute(action)
