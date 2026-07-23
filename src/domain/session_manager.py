"""会话管理器

管理诊断会话的 CRUD 和生命周期。
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.core.models import (
    DiagnosisSession,
    DiagnosisSummary,
    FaultContext,
    SessionStatus,
)
from src.core.exceptions import SessionNotFoundError
from src.infrastructure.event_bus import EventBus
from src.infrastructure.line_normalizer import LineNormalizer
from src.infrastructure.session_repository import SessionRepository
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        event_bus: EventBus,
        state_machine: StateMachine,
        repository: Optional[SessionRepository] = None,
    ):
        self.event_bus = event_bus
        self.state_machine = state_machine
        self.repository = repository
        self._default_skill_name: str = "comprehensive_diagnosis"

        if repository is not None:
            self._sessions = repository.load_all()
            self._active_session_id = None
        else:
            self._sessions: Dict[str, DiagnosisSession] = {}
            self._active_session_id = None

    def _persist(self) -> None:
        """持久化当前会话状态"""
        if self.repository is not None:
            try:
                self.repository.save_all(self._sessions)
            except Exception:
                logger.exception("会话持久化失败")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self, line_name: str, fault_context: Optional[FaultContext] = None
    ) -> DiagnosisSession:
        """创建新会话，从当前激活技能加载权重"""
        normalized = LineNormalizer.normalize(line_name)
        session = DiagnosisSession(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            line_name=normalized,
            status=SessionStatus.PENDING,
            fault_context=fault_context,
        )
        session.active_skill_name = self._default_skill_name

        # 继承全局激活模板
        try:
            from src.domain.template_registry import TemplateRegistry

            registry = TemplateRegistry()
            active_template = registry.get_active()
            if active_template:
                session.active_template_name = active_template
        except Exception:
            pass  # 模板注册表失败不应阻塞会话创建

        # 从技能文件加载权重
        skill_weights = self._load_skill_weights(session.active_skill_name)
        if skill_weights:
            session.active_weights = skill_weights.copy()
        else:
            from src.core.models import DEFAULT_WEIGHTS
            session.active_weights = DEFAULT_WEIGHTS.copy()

        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id

        logger.info(f"创建会话: {session.session_id} ({normalized})")
        self._persist()
        return session

    def _load_skill_weights(self, skill_name: str) -> dict[str, float]:
        """从技能文件加载权重配置"""
        try:
            from src.domain.skill_loader import SkillLoader
            loader = SkillLoader()
            _, weights = loader.load(skill_name)
            return weights
        except Exception:
            return {}

    def get(self, session_id: str) -> DiagnosisSession:
        """获取会话"""
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"会话不存在: {session_id}")
        return self._sessions[session_id]

    def get_active(self) -> Optional[DiagnosisSession]:
        """获取当前活跃会话"""
        if not self._active_session_id:
            return None
        return self._sessions.get(self._active_session_id)

    def get_or_create(
        self, line_name: str, fault_context: Optional[FaultContext] = None
    ) -> DiagnosisSession:
        """获取或创建会话

        同一线路（标准化后）且未完成的会话会被复用。
        如果提供了 fault_context，还会匹配电压等级和故障时间。
        """
        normalized = LineNormalizer.normalize(line_name)

        # 查找现有未完成会话
        for sess in self._sessions.values():
            if sess.status == SessionStatus.COMPLETED:
                continue
            if LineNormalizer.normalize(sess.line_name) != normalized:
                continue

            # 若提供了 fault_context，进行更精确匹配
            if fault_context:
                # 匹配电压等级
                input_voltage = fault_context.additional_info.get("voltage_level", "")
                sess_voltage = ""
                if sess.current_summary and sess.current_summary.fault_context:
                    sess_voltage = (
                        sess.current_summary.fault_context.additional_info.get(
                            "voltage_level", ""
                        )
                        or ""
                    )
                if input_voltage and sess_voltage and input_voltage != sess_voltage:
                    continue

                # 匹配故障时间（仅比较日期部分）
                input_time = fault_context.fault_time
                if input_time and sess.current_summary and sess.current_summary.fault_context:
                    sess_time = sess.current_summary.fault_context.fault_time
                    if sess_time and input_time.strftime("%Y-%m-%d") != sess_time.strftime("%Y-%m-%d"):
                        continue

            self._active_session_id = sess.session_id
            logger.info(f"复用会话: {sess.session_id} ({normalized})")
            return sess

        # 创建新会话
        return self.create(line_name, fault_context=fault_context)
    def set_default_skill(self, name: str) -> None:
        """设置全局默认技能"""
        self._default_skill_name = name
        logger.info(f"设置默认技能: {name}")

    def list_sessions(self) -> List[DiagnosisSession]:
        """列出所有会话"""
        return list(self._sessions.values())

    def switch_active(self, session_id: str) -> DiagnosisSession:
        """切换活跃会话"""
        session = self.get(session_id)
        self._active_session_id = session_id
        logger.info(f"切换活跃会话: {session_id}")
        return session

    # ------------------------------------------------------------------
    # 状态管理
    # ------------------------------------------------------------------

    def transition(self, session_id: str, target: SessionStatus) -> None:
        """转换会话状态"""
        session = self.get(session_id)
        self.state_machine.transition(session, target)
        self._persist()

    # ------------------------------------------------------------------
    # 诊断历史
    # ------------------------------------------------------------------

    def add_summary(self, session_id: str, summary: DiagnosisSummary) -> None:
        """添加诊断摘要"""
        session = self.get(session_id)
        session.summaries.append(summary)
        session.current_summary = summary
        session.updated_at = datetime.now()
        self._persist()

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def update_weights(
        self, session_id: str, weights: Dict[str, float]
    ) -> None:
        """更新会话权重"""
        session = self.get(session_id)
        session.active_weights = {**session.active_weights, **weights}
        session.updated_at = datetime.now()
        self._persist()
        logger.info(f"更新权重: {session_id} -> {weights}")

    def exclude_tool(self, session_id: str, tool_name: str) -> None:
        """排除工具"""
        session = self.get(session_id)
        if tool_name not in session.excluded_tools:
            session.excluded_tools.append(tool_name)
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"排除工具: {session_id} -> {tool_name}")

    def include_tool(self, session_id: str, tool_name: str) -> None:
        """恢复工具"""
        session = self.get(session_id)
        if tool_name in session.excluded_tools:
            session.excluded_tools.remove(tool_name)
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"恢复工具: {session_id} -> {tool_name}")

    def exclude_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量排除工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name not in session.excluded_tools:
                session.excluded_tools.append(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量排除工具: {session_id} -> {tool_names}")

    def include_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量恢复工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name in session.excluded_tools:
                session.excluded_tools.remove(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量恢复工具: {session_id} -> {tool_names}")

    def add_rechecked(self, session_id: str, tool_name: str) -> None:
        """记录重新检查"""
        session = self.get(session_id)
        if tool_name not in session.rechecked_tools:
            session.rechecked_tools.append(tool_name)
            session.updated_at = datetime.now()
            self._persist()
