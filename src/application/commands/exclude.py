"""排除工具 Command"""

import logging
from typing import AsyncIterator, List

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError, ToolNotFoundError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class ExcludeToolCommand(Command):
    """排除工具 Command

    从会话中排除指定工具，更新 excluded_tools 列表，
    并将会话状态转换到 EXCLUDED。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行排除工具操作"""
        session = ctx.session
        tool_names = self._extract_tool_names(ctx)

        yield Event.thinking(session.session_id, f"准备排除工具: {', '.join(tool_names)}...")

        self._validate_state(session)
        for tool_name in tool_names:
            self._validate_tool_exists(tool_name)

        self.session_manager.exclude_tools(session.session_id, tool_names)
        for tool_name in tool_names:
            session.action_log.append(
                UserAction(
                    action_type="exclude",
                    parameters={"tool_name": tool_name},
                )
            )
        # 保持在 MODIFYING 状态，用户可以继续调整或重新诊断
        if session.status != SessionStatus.MODIFYING:
            self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)
            yield Event.status(
                session.session_id,
                {"status": SessionStatus.MODIFYING.value},
            )

        logger.info(f"已排除工具: {session.session_id} -> {tool_names}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已排除工具: {', '.join(tool_names)}",
                "excluded_tools": session.excluded_tools,
                "status": session.status.value,
            },
        )

    def _extract_tool_names(self, ctx: ExecutionContext) -> List[str]:
        """从意图参数中提取工具名列表"""
        if ctx.intent:
            params = ctx.intent.parameters
            # 优先使用 tool_names（多工具）
            tool_names = params.get("tool_names", [])
            if tool_names:
                return tool_names
            # 回退到单 tool_name
            tool_name = params.get("tool_name", "")
            if tool_name:
                return [tool_name]
        raise InvalidStateError("缺少 tool_name/tool_names 参数")

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许排除操作"""
        if not self.state_machine.can_execute(session, "exclude"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许排除工具"
            )

    def _validate_tool_exists(self, tool_name: str) -> None:
        """验证工具是否存在（占位，实际可通过 registry 校验）"""
        if not tool_name:
            raise ToolNotFoundError("工具名不能为空")
