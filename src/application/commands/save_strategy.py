"""保存策略 Command"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, Strategy
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)

DEFAULT_STRATEGIES_DIR = Path("skills")


class SaveStrategyCommand(Command):
    """保存策略 Command

    将当前会话的配置保存为策略（Strategy），
    包括工具权重、排除工具列表、模板名称，
    持久化到 skills/ 目录下的 JSON 文件。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
        strategies_dir: Path | None = None,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.strategies_dir = strategies_dir or DEFAULT_STRATEGIES_DIR

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行保存策略操作"""
        session = ctx.session
        strategy_name = self._extract_strategy_name(ctx)

        yield Event.thinking(
            session.session_id,
            f"保存策略: {strategy_name}...",
        )

        self._validate_state(session)
        self._ensure_strategies_dir()

        strategy = self._build_strategy(session, strategy_name)
        file_path = self._save_to_file(strategy)

        session.custom_strategy_name = strategy_name
        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)

        logger.info(f"策略已保存: {session.session_id} -> {file_path}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"策略 '{strategy_name}' 已保存",
                "strategy_name": strategy_name,
                "file_path": str(file_path),
                "tool_weights": strategy.tool_weights,
                "excluded_tools": strategy.excluded_tools,
                "template_name": strategy.template_name,
            },
        )

    def _extract_strategy_name(self, ctx: ExecutionContext) -> str:
        """从意图参数中提取策略名称"""
        if ctx.intent:
            name = ctx.intent.parameters.get("strategy_name", "")
            if name:
                return name
        return f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许保存策略"""
        if not self.state_machine.can_execute(session, "save_strategy"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许保存策略"
            )

    def _ensure_strategies_dir(self) -> None:
        """确保策略目录存在"""
        self.strategies_dir.mkdir(parents=True, exist_ok=True)

    def _build_strategy(self, session, name: str) -> Strategy:
        """从会话构建策略对象"""
        template_name = session.custom_strategy_name or "default"
        return Strategy(
            name=name,
            description=f"从会话 {session.session_id} 导出的策略",
            tool_weights=session.active_weights.copy(),
            excluded_tools=session.excluded_tools.copy(),
            template_name=template_name,
        )

    def _save_to_file(self, strategy: Strategy) -> Path:
        """将策略持久化到 JSON 文件"""
        file_path = self.strategies_dir / f"{strategy.name}.json"
        data = strategy.model_dump(mode="json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return file_path
