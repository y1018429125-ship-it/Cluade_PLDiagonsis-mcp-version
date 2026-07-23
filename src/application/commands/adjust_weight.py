"""调整权重 Command"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError, WeightValidationError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)

WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0


class AdjustWeightCommand(Command):
    """调整权重 Command

    调整指定工具的权重，验证范围后更新 active_weights。
    纯状态更新，不重新计算加权结果（由 LLM 通过 Skill 自主计算）。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行权重调整操作"""
        session = ctx.session
        tool_name, new_weight = self._extract_params(ctx)

        yield Event.thinking(
            session.session_id,
            f"调整 {tool_name} 权重为 {new_weight}...",
        )

        self._validate_state(session)
        self._validate_weight(tool_name, new_weight)

        self.session_manager.update_weights(
            session.session_id, {tool_name: new_weight}
        )
        session.action_log.append(
            UserAction(
                action_type="adjust_weight",
                parameters={"tool_name": tool_name, "weight": new_weight},
            )
        )

        logger.info(f"权重调整完成: {session.session_id} -> {tool_name}={new_weight}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已调整 {tool_name} 权重为 {new_weight}",
                "active_weights": session.active_weights,
            },
        )

    def _extract_params(self, ctx: ExecutionContext) -> tuple[str, float]:
        """从意图参数中提取工具名和新权重"""
        if not ctx.intent:
            raise InvalidStateError("缺少意图参数")

        tool_name = ctx.intent.parameters.get("tool_name", "")
        weight_raw = ctx.intent.parameters.get("weight")

        if not tool_name:
            raise InvalidStateError("缺少 tool_name 参数")
        if weight_raw is None:
            raise InvalidStateError("缺少 weight 参数")

        try:
            new_weight = float(weight_raw)
        except (ValueError, TypeError) as exc:
            raise InvalidStateError(f"权重值无效: {weight_raw}") from exc

        return tool_name, new_weight

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许调整权重"""
        if not self.state_machine.can_execute(session, "adjust_weight"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许调整权重"
            )

    def _validate_weight(self, tool_name: str, weight: float) -> None:
        """验证权重范围"""
        if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
            raise WeightValidationError(
                f"权重 {tool_name}={weight} 超出范围 [{WEIGHT_MIN}, {WEIGHT_MAX}]"
            )
