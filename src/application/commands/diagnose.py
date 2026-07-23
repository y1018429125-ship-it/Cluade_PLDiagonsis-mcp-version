"""诊断 Command"""

import asyncio
import logging
import time
from typing import AsyncIterator

from src.core.models import (
    ConfidenceLevel,
    DiagnosisContext,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisSummary,
    Event,
    ExecutionContext,
    FaultContext,
    SessionStatus,
)
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.diagnosis_planner import DiagnosisPlanner
from src.domain.prompt_builder import PromptBuilder
from src.domain.report_composer import ReportComposer
from src.domain.skill_loader import SkillLoader
from src.domain.tool_executor import ToolExecutor
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.diagnosis_logger import DiagnosisLogger
from src.infrastructure.event_bus import EventBus
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class DiagnoseCommand(Command):
    """诊断 Command"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        session_manager: SessionManager,
        state_machine: StateMachine,
        event_bus: EventBus,
        skill_loader: SkillLoader,
        prompt_builder: PromptBuilder,
        diagnosis_planner: DiagnosisPlanner,
        tool_executor: ToolExecutor,
        report_composer: ReportComposer,
    ):
        self.tool_registry = tool_registry
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.skill_loader = skill_loader
        self.prompt_builder = prompt_builder
        self.diagnosis_planner = diagnosis_planner
        self.tool_executor = tool_executor
        self.report_composer = report_composer

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行诊断"""
        session = ctx.session
        diag_logger: DiagnosisLogger | None = getattr(ctx, "diagnosis_logger", None)

        def _log_stage_start(stage: str, details: dict | None = None) -> None:
            if diag_logger:
                diag_logger.start_stage(stage, details)

        def _log_stage_end(stage: str, details: dict | None = None) -> None:
            if diag_logger:
                diag_logger.end_stage(stage, details)

        # 全新诊断时清除缓存（必须在状态转换前检查）
        is_fresh_diagnosis = session.status == SessionStatus.PENDING
        if is_fresh_diagnosis:
            session.tool_outputs_cache.clear()

        # 1. 验证状态并转换到诊断中
        if not self.state_machine.can_execute(session, "diagnose"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许执行诊断"
            )

        _log_stage_start("state_transition")
        yield Event.start(session.session_id, "开始故障诊断...")
        self.session_manager.transition(
            session.session_id, SessionStatus.DIAGNOSING
        )
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.DIAGNOSING.value},
        )
        _log_stage_end("state_transition")

        # 2. 解析故障上下文
        _log_stage_start("parse_fault_context")
        fault_context = self._parse_fault_context(ctx.user_message, session)
        yield Event.thinking(
            session.session_id, f"解析线路信息: {fault_context.line_name}"
        )
        _log_stage_end("parse_fault_context", {"line_name": fault_context.line_name})

        # 3. 加载诊断技能
        _log_stage_start("load_skill")
        yield Event.thinking(session.session_id, "加载诊断技能...")
        skill_name = session.active_skill_name or "comprehensive_diagnosis"
        skill_md, _ = self.skill_loader.load(skill_name)
        _log_stage_end("load_skill", {"skill_name": skill_name})

        # 4. 扫描诊断工具
        _log_stage_start("list_tools")
        yield Event.thinking(session.session_id, "扫描诊断工具...")
        available_tools = self.tool_registry.list_tools()
        _log_stage_end("list_tools", {"tool_count": len(available_tools)})

        # 5. 构建诊断计划
        _log_stage_start("build_prompt")
        yield Event.thinking(session.session_id, "构建诊断计划...")
        prompt = self.prompt_builder.build(
            skill_md, session, available_tools, ctx.user_message
        )
        _log_stage_end("build_prompt")

        # 6. AI 制定诊断方案（流式输出思考过程）
        _log_stage_start("ai_planning")
        yield Event.thinking(session.session_id, "AI 正在制定诊断方案...")
        queue: asyncio.Queue[str] = asyncio.Queue()
        thinking_parts: list[str] = []

        def on_chunk(chunk: str) -> None:
            queue.put_nowait(chunk)

        plan_task = asyncio.create_task(
            self.diagnosis_planner.plan(prompt, on_chunk=on_chunk)
        )

        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.05)
                thinking_parts.append(chunk)
                yield Event.thinking(
                    session.session_id, "".join(thinking_parts)
                )
            except asyncio.TimeoutError:
                if plan_task.done():
                    while not queue.empty():
                        thinking_parts.append(queue.get_nowait())
                    break

        plan = plan_task.result()
        thinking_text = "".join(thinking_parts)
        tool_names = [t["name"] for t in plan.get("tools_to_call", [])]
        _log_stage_end(
            "ai_planning",
            {"planned_tools": tool_names, "report_structure": plan.get("report_structure", [])},
        )
        yield Event.thinking(
            session.session_id,
            f"诊断计划: 调用 {', '.join(tool_names)} | "
            f"报告结构: {', '.join(plan.get('report_structure', []))}",
        )

        # 7. 执行诊断工具（带缓存复用）
        _log_stage_start("execute_tools")
        yield Event.thinking(session.session_id, "执行诊断工具...")
        diagnosis_ctx = DiagnosisContext(
            session_id=session.session_id,
            line_name=session.line_name,
            weights=session.active_weights.copy(),
            excluded_tools=session.excluded_tools.copy(),
            rechecked_tools=session.rechecked_tools.copy(),
            fault_context=fault_context,
        )
        # 将 logger 注入执行上下文，供 ToolExecutor 记录单个工具耗时
        if diag_logger:
            object.__setattr__(diagnosis_ctx, "diagnosis_logger", diag_logger)

        planned_tools = plan.get("tools_to_call", [])
        planned_names = {t["name"] for t in planned_tools}

        # 分类：缓存复用 vs 需要调用
        cached_outputs = {}
        names_to_call = []

        for tool_name in planned_names:
            if tool_name in session.tool_outputs_cache:
                cached_outputs[tool_name] = session.tool_outputs_cache[tool_name]
                yield Event.thinking(
                    session.session_id, f"复用 {tool_name} 历史数据..."
                )
            else:
                names_to_call.append(tool_name)

        # 只调用未缓存的工具
        if names_to_call:
            partial_plan = {
                "tools_to_call": [t for t in planned_tools if t["name"] in names_to_call],
                "parallel": plan.get("parallel", True),
            }
            tools_start = time.perf_counter()
            new_outputs = await self.tool_executor.execute(partial_plan, diagnosis_ctx)
            tools_end = time.perf_counter()
            if diag_logger:
                diag_logger.record_tool_timing(
                    "all_tools", tools_start, tools_end, success=True
                )
        else:
            new_outputs = {}

        # 合并结果
        tool_outputs = {**cached_outputs, **new_outputs}

        # 新结果存入缓存
        for name, output in new_outputs.items():
            session.tool_outputs_cache[name] = output

        _log_stage_end("execute_tools", {"tool_count": len(tool_outputs)})

        # 8. 输出每个工具的结果
        for name, output in tool_outputs.items():
            yield Event.result(
                session.session_id,
                {"tool": name, "output": output.model_dump(mode="json")},
            )

        # 9. 生成诊断报告
        _log_stage_start("compose_report")
        yield Event.thinking(session.session_id, "生成诊断报告...")
        action_log_data = [
            {
                "action_type": a.action_type,
                "tool_name": a.parameters.get("tool_name", ""),
                "description": a.parameters.get("description", ""),
                "weight": a.parameters.get("weight"),
            }
            for a in session.action_log
        ]
        compose_start = time.perf_counter()
        composed = await self.report_composer.compose(
            tool_outputs, None, session.session_id, fault_context, action_log_data,
            weights=session.active_weights,
            active_template_name=session.active_template_name,
            active_skill_name=session.active_skill_name,
        )
        compose_end = time.perf_counter()
        if diag_logger:
            diag_logger.record_tool_timing(
                "report_composer", compose_start, compose_end, success=True
            )
        report = composed["report"]
        summary = composed["summary"]
        session.latest_report = report
        _log_stage_end("compose_report")

        # 10. 创建诊断摘要并保存到会话
        _log_stage_start("save_summary")
        confidence_level = (
            ConfidenceLevel.HIGH if summary['confidence'] >= 0.7
            else ConfidenceLevel.MEDIUM if summary['confidence'] >= 0.4
            else ConfidenceLevel.LOW
        )
        diagnosis_summary = DiagnosisSummary(
            fault_context=fault_context,
            primary_diagnosis=DiagnosisResult(
                fault_type=summary['fault_type'],
                confidence=summary['confidence'],
                confidence_level=confidence_level,
                tool_name=summary.get('primary_tool', 'unknown'),
            ),
        )
        self.session_manager.add_summary(session.session_id, diagnosis_summary)
        _log_stage_end("save_summary")

        # 11. 转换到可修改状态
        _log_stage_start("final_state_transition")
        self.session_manager.transition(
            session.session_id, SessionStatus.MODIFYING
        )
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.MODIFYING.value},
        )
        _log_stage_end("final_state_transition")

        yield Event.complete(
            session.session_id,
            {
                "summary": summary,
                "report": report,
                "message": f"诊断完成：{summary['fault_type']}（置信度 {int(summary['confidence'] * 100)}%）",
                "thinking": thinking_text,
                "action_log": action_log_data,
                "status": SessionStatus.MODIFYING.value,
            },
        )

    def _parse_fault_context(
        self, message: str, session: DiagnosisSession
    ) -> FaultContext:
        """解析故障上下文。

        优先从用户消息中提取，若缺失关键字段则回退到会话已保存的 fault_context。
        """
        from src.infrastructure.fault_parser import FaultContextParser

        fault_ctx = FaultContextParser.parse(message, session.line_name)
        fault_ctx.line_id = session.session_id

        # 若用户消息未提供故障时间/电压等级，回退到会话原始 fault_context
        if session.fault_context:
            if not fault_ctx.fault_time and session.fault_context.fault_time:
                fault_ctx.fault_time = session.fault_context.fault_time
            if not fault_ctx.additional_info.get("voltage_level") and session.fault_context.additional_info.get("voltage_level"):
                fault_ctx.additional_info["voltage_level"] = session.fault_context.additional_info["voltage_level"]

        return fault_ctx
