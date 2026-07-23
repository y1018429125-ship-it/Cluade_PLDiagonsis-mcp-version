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
        mock_llm_service.chat = AsyncMock(
            return_value='{"thought":"完成","action":"finish","answer":"武汉晴 25°C"}'
        )

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
        )

        result = await loop.run("查询武汉天气")
        assert result == "武汉晴 25°C"
        mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_executes_multiple_steps(self, mock_llm_service, mock_controller, mock_executor):
        """多步任务：先 navigate，后 finish"""
        mock_llm_service.chat = AsyncMock(side_effect=[
            '{"thought":"去百度","action":"navigate","value":"https://baidu.com"}',
            '{"thought":"完成","action":"finish","answer":"结果"}',
        ])

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
        )

        result = await loop.run("查询天气")
        assert result == "结果"
        assert mock_executor.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_run_strips_markdown_code_block(self, mock_llm_service, mock_controller, mock_executor):
        """LLM 返回 markdown 代码块时应正确解析"""
        mock_llm_service.chat = AsyncMock(
            return_value='```json\n{"thought":"done","action":"finish","answer":"ok"}\n```'
        )

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
        )

        result = await loop.run("task")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_run_raises_on_invalid_json(self, mock_llm_service, mock_controller, mock_executor):
        """LLM 返回非 JSON 时应抛出 ValueError"""
        mock_llm_service.chat = AsyncMock(return_value="not json")

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
        )

        with pytest.raises(ValueError, match="非 JSON"):
            await loop.run("task")

    @pytest.mark.asyncio
    async def test_run_max_steps_reached(self, mock_llm_service, mock_controller, mock_executor):
        """达到 max_steps 时返回未完成信息"""
        mock_llm_service.chat = AsyncMock(
            return_value='{"thought":"继续","action":"wait"}'
        )

        loop = AgentLoop(
            llm_service=mock_llm_service,
            controller=mock_controller,
            executor=mock_executor,
            max_steps=2,
        )

        result = await loop.run("task")
        assert "未在 2 步内完成" in result
