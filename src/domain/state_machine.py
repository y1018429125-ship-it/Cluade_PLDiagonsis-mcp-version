"""状态机

管理会话状态的生命周期和转换规则。
禁止直接修改 session.status，所有转换必须经过 StateMachine。
"""

import logging
from typing import Dict, List, Optional

from src.core.models import DiagnosisSession, Event, SessionStatus
from src.core.exceptions import InvalidStateError
from src.infrastructure.event_bus import EventBus

logger = logging.getLogger(__name__)

# 有效的状态转换图
VALID_TRANSITIONS: Dict[SessionStatus, List[SessionStatus]] = {
    SessionStatus.PENDING: [SessionStatus.DIAGNOSING],
    SessionStatus.DIAGNOSING: [
        SessionStatus.MODIFYING,
        SessionStatus.EXCLUDED,
        SessionStatus.RECHECKING,
    ],
    SessionStatus.MODIFYING: [
        SessionStatus.COMPLETED,
        SessionStatus.EXCLUDED,
        SessionStatus.RECHECKING,
        SessionStatus.MODIFYING,
        SessionStatus.DIAGNOSING,
    ],
    SessionStatus.COMPLETED: [
        SessionStatus.RECHECKING,
        SessionStatus.MODIFYING,
    ],
    SessionStatus.EXCLUDED: [
        SessionStatus.MODIFYING,
        SessionStatus.RECHECKING,
    ],
    SessionStatus.RECHECKING: [
        SessionStatus.MODIFYING,
        SessionStatus.EXCLUDED,
    ],
}

# 各状态允许的 Command 类型
STATE_COMMAND_PERMISSIONS: Dict[SessionStatus, List[str]] = {
    SessionStatus.PENDING: ["diagnose"],
    SessionStatus.DIAGNOSING: ["exclude", "recheck"],
    SessionStatus.MODIFYING: [
        "modify",
        "modify_report",
        "exclude",
        "recheck",
        "adjust_weight",
        "complete",
        "save_strategy",
        "diagnose",
        "include",
    ],
    SessionStatus.COMPLETED: ["recheck", "modify", "modify_report", "save_strategy"],
    SessionStatus.EXCLUDED: ["modify", "recheck", "adjust_weight", "diagnose", "include"],
    SessionStatus.RECHECKING: ["modify", "exclude", "adjust_weight"],
}


class StateMachine:
    """状态机"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    def can_transition(
        self, session: DiagnosisSession, target: SessionStatus
    ) -> bool:
        """检查状态转换是否合法"""
        current = session.status
        valid_targets = VALID_TRANSITIONS.get(current, [])
        return target in valid_targets

    def can_execute(self, session: DiagnosisSession, command_type: str) -> bool:
        """检查当前状态是否允许执行指定 Command"""
        allowed = STATE_COMMAND_PERMISSIONS.get(session.status, [])
        return command_type in allowed

    def transition(
        self,
        session: DiagnosisSession,
        target: SessionStatus,
        metadata: Optional[dict] = None,
    ) -> None:
        """执行状态转换"""
        current = session.status

        if not self.can_transition(session, target):
            raise InvalidStateError(
                f"非法状态转换: {current.value} -> {target.value}",
                details={"current": current.value, "target": target.value},
            )

        # 记录转换前状态
        old_status = current

        # 执行转换
        session.status = target
        from datetime import datetime
        session.updated_at = datetime.now()

        logger.info(f"会话 {session.session_id}: {old_status.value} -> {target.value}")

        # 发布状态变更事件
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            coro = self.event_bus.publish(
                Event.status(
                    session.session_id,
                    {"status": target.value, "previous": old_status.value},
                )
            )
            loop.create_task(coro)
