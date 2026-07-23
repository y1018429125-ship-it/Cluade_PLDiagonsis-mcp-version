"""修改报告 Command"""

import logging
from pathlib import Path
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.skill_loader import SkillLoader
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)


class ModifyReportCommand(Command):
    """修改报告 Command

    基于用户自然语言指令，LLM 理解意图后重写报告。
    """

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skill_loader: SkillLoader,
    ):
        self.llm = llm_service
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skill_loader = skill_loader

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行报告修改"""
        session = ctx.session
        instruction = ctx.user_message

        yield Event.thinking(session.session_id, "理解修改指令...")

        if not self.state_machine.can_execute(session, "modify_report"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许修改报告"
            )

        current_report = session.latest_report
        if not current_report:
            yield Event.error(session.session_id, "当前没有可修改的报告")
            return

        # 加载报告修改 Skill
        skill_md, _ = self.skill_loader.load("report_modifier")

        # 加载当前激活模板作为约束
        template_md = ""
        if session.active_template_name:
            parsed_path = Path("templates/parsed") / f"{session.active_template_name}.md"
            if parsed_path.exists():
                template_md = parsed_path.read_text(encoding="utf-8")

        prompt = f"""你是输电线路故障诊断报告编辑专家。

## 当前报告
{current_report}

## 用户修改指令
{instruction}

## 修改指导
{skill_md}

## 模板约束（必须遵守的章节结构）
{template_md or "使用默认章节结构：概述 / 故障分析 / 诊断证据 / 诊断结论 / 处理建议"}

## 修改要求
1. 严格理解用户意图，精确执行修改
2. 保持报告的专业性和逻辑连贯性
3. 不删除用户未要求删除的内容
4. 修改后报告必须符合模板章节结构
5. 如果用户要求调整章节顺序，在保持内容完整的前提下重新组织

请输出修改后的完整报告。
"""

        yield Event.thinking(session.session_id, "正在修改报告...")

        modified_report = await self.llm.chat([
            {"role": "system", "content": "你是输电线路故障诊断报告编辑专家。"},
            {"role": "user", "content": prompt},
        ])

        # 记录修改操作
        session.action_log.append(
            UserAction(
                action_type="modify_report",
                parameters={
                    "instruction": instruction,
                    "before_length": len(current_report),
                    "after_length": len(modified_report),
                },
            )
        )

        session.latest_report = modified_report
        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)
        self.session_manager._persist()

        logger.info(
            f"报告已修改: {session.session_id}, "
            f"before={len(current_report)}, after={len(modified_report)}"
        )

        # 构建 summary 供前端渲染诊断卡片
        primary = session.current_summary.primary_diagnosis if session.current_summary else None
        summary = {
            "fault_type": primary.fault_type if primary else "未知",
            "confidence": primary.confidence if primary else 0.0,
            "line_name": session.line_name or "",
            "voltage_level": session.fault_context.additional_info.get("voltage_level", "") if session.fault_context else "",
            "fault_time": session.fault_context.fault_time.isoformat() if session.fault_context and session.fault_context.fault_time else "",
            "action_log": [
                {
                    "action_type": a.action_type,
                    "tool_name": a.parameters.get("tool_name", ""),
                    "description": a.parameters.get("description", ""),
                    "weight": a.parameters.get("weight"),
                }
                for a in session.action_log
            ],
        }

        yield Event.complete(
            session.session_id,
            {
                "message": "报告已按您的要求修改",
                "report": modified_report,
                "summary": summary,
                "status": "modifying",
            },
        )
