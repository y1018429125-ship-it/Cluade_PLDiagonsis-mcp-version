"""Flask Web 接口

仅负责路由和 SSE 流式输出，不处理业务逻辑。
Flask 3.x 原生支持 async 视图函数，无需额外包装。
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict

import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from src.core.models import Event, EventType, IntentType, SessionStatus
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.include_tool import IncludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.adjust_weight import AdjustWeightCommand
from src.application.commands.save_strategy import SaveStrategyCommand
from src.application.commands.complete_diagnosis import CompleteDiagnosisCommand
from src.application.commands.modify_report import ModifyReportCommand
from src.application.context import ContextBuilder
from src.interfaces.dependency_injection import get_container
from src.infrastructure.fault_parser import FaultContextParser
from src.infrastructure.diagnosis_logger import DiagnosisLogger
from src.domain.template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


def _serialize_payload(obj: Any) -> Any:
    """序列化日志负载，处理 datetime 等不可 JSON 序列化的类型。"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_payload(v) for v in obj]
    return obj


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    container = get_container()

    @app.before_request
    def _ensure_container_init() -> None:
        """确保容器已初始化（惰性初始化）"""
        if not getattr(container, "_initialized", False):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # 在异步上下文中，使用 create_task 初始化
                asyncio.create_task(container.init())
            else:
                asyncio.run(container.init())
            container._initialized = True

    # ------------------------------------------------------------------
    # SSE 聊天接口
    # ------------------------------------------------------------------
    @app.route("/chat", methods=["POST"])
    def chat():
        """流式对话接口"""
        data = request.json or {}
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "消息不能为空"}), 400

        return Response(
            stream_with_context(_sync_chat_stream(user_message)),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    def _sync_chat_stream(message: str):
        """同步包装器：将 async generator 桥接到 Flask WSGI"""
        async def _async_stream():
            async for event in _chat_stream(message):
                yield event

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = _async_stream()
        try:
            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def _append_chat_message(session, role: str, content: str, event_type: str = None):
        """追加聊天记录到会话"""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if event_type:
            msg["event_type"] = event_type
        session.chat_history.append(msg)

    async def _chat_stream(message: str):
        """聊天流生成器（异步）"""
        session = None
        diag_logger: DiagnosisLogger | None = None
        try:
            # 1. 意图识别（先识别意图，再决定如何获取会话）
            intent = await container.intent_classifier.classify(message, None)
            intent_type = intent.intent_type

            # 2. 获取会话：诊断类意图从消息中提取线路，其他意图使用活跃会话
            if intent_type == IntentType.DIAGNOSE:
                fault_ctx = FaultContextParser.parse(message, "")
                line_name = fault_ctx.line_name or message
                session = container.session_manager.get_or_create(
                    line_name, fault_context=fault_ctx
                )
            else:
                session = container.session_manager.get_active()
                if session is None:
                    yield _sse_event(
                        Event.error("", "没有活跃的会话，请先开始诊断")
                    )
                    return

            # 初始化诊断日志记录器
            diag_logger = DiagnosisLogger(
                session_id=session.session_id,
                line_name=session.line_name,
                user_message=message,
            )
            _active_loggers[session.session_id] = diag_logger

            # 保存用户消息
            _append_chat_message(session, "user", message)

            start_payload: dict[str, Any] = {
                "message": "开始诊断...",
                "line_name": session.line_name,
            }
            if session.fault_context:
                if session.fault_context.fault_time:
                    start_payload["fault_time"] = session.fault_context.fault_time.isoformat()
                voltage = session.fault_context.additional_info.get("voltage_level")
                if voltage:
                    start_payload["voltage_level"] = voltage
            yield _sse_event(
                Event.start(
                    session.session_id,
                    start_payload,
                )
            )
            yield _sse_event(Event.thinking(session.session_id, "理解用户意图..."))

            # 重新分类（带会话上下文）以获得更准确的参数提取
            intent = await container.intent_classifier.classify(message, session)

            # 3. 构建执行上下文
            ctx = ContextBuilder.build(session, message, intent=intent, diagnosis_logger=diag_logger)

            # 4. 路由到对应 Command
            cmd = _resolve_command(intent.intent_type, container)
            if cmd is not None:
                async for event in cmd.execute(ctx):
                    if diag_logger:
                        diag_logger.record_event(
                            event.event_type.value,
                            _serialize_payload(event.payload),
                        )
                    yield _sse_event(event)
                    if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                        _append_chat_message(
                            session,
                            "assistant",
                            event.payload.get("message", ""),
                            event.event_type.value,
                        )

                # 自动链式诊断：排除/恢复/调整权重后无条件自动重新诊断
                if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL, IntentType.ADJUST_WEIGHT):
                    yield _sse_event(
                        Event.thinking(session.session_id, "自动重新诊断...")
                    )

                    # 重建 diagnose 上下文（确保使用当前会话状态）
                    from src.core.models import Intent
                    diagnose_intent = Intent(
                        intent_type=IntentType.DIAGNOSE,
                        confidence=1.0,
                        parameters={},
                    )
                    ctx = ContextBuilder.build(
                        session, message, intent=diagnose_intent, diagnosis_logger=diag_logger
                    )

                    diagnose_cmd = DiagnoseCommand(
                        tool_registry=container.tool_registry,
                        session_manager=container.session_manager,
                        state_machine=container.state_machine,
                        event_bus=container.event_bus,
                        skill_loader=container.skill_loader,
                        prompt_builder=container.prompt_builder,
                        diagnosis_planner=container.diagnosis_planner,
                        tool_executor=container.tool_executor,
                        report_composer=container.report_composer,
                    )
                    async for event in diagnose_cmd.execute(ctx):
                        if diag_logger:
                            diag_logger.record_event(
                                event.event_type.value,
                                _serialize_payload(event.payload),
                            )
                        yield _sse_event(event)
                        if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                            _append_chat_message(
                                session,
                                "assistant",
                                event.payload.get("message", ""),
                                event.event_type.value,
                            )
            else:
                # 非诊断相关对话，提示用户
                hint = (
                    "您好，我是输电线路故障综合诊断智能体，专注于输电线路跳闸等故障的诊断分析。"
                    "请提供线路名称、电压等级及故障时间等信息，我将为您进行专业诊断。"
                )
                yield _sse_event(Event.complete(session.session_id, {"message": hint}))
                _append_chat_message(session, "assistant", hint, EventType.COMPLETE.value)

            # 持久化聊天记录
            container.session_manager._persist()

        except Exception as e:
            logger.error(f"处理失败: {e}")
            yield _sse_event(Event.error("", str(e)))
            if session:
                _append_chat_message(session, "assistant", str(e), EventType.ERROR.value)
                container.session_manager._persist()
        finally:
            if diag_logger:
                diag_logger.finalize()
                # finalize 后从活跃记录器中移除，但保留文件路径便于前端合并时加载
                _active_loggers.pop(session.session_id, None)

    # ------------------------------------------------------------------
    # 前端日志合并接口
    # ------------------------------------------------------------------
    _active_loggers: Dict[str, DiagnosisLogger] = {}

    @app.route("/api/log/frontend", methods=["POST"])
    def receive_frontend_log():
        """接收前端日志并合并到同一请求的诊断日志中。"""
        data = request.json or {}
        session_id = data.get("session_id", "").strip()
        frontend_log = data.get("frontend_log")

        if not session_id or not isinstance(frontend_log, dict):
            return jsonify({"error": "缺少 session_id 或 frontend_log"}), 400

        diag_logger = _active_loggers.get(session_id)
        if diag_logger is None:
            # 如果 logger 已被 finalize 清理，尝试从当天日志中查找并追加
            diag_logger = _load_existing_logger(session_id)
            if diag_logger is None:
                return jsonify({"error": "未找到对应会话的诊断日志"}), 404

        try:
            diag_logger.merge_frontend_log(frontend_log)
            # 前端日志到达后重新保存（覆盖原文件）
            diag_logger.finalize()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"合并前端日志失败 {session_id}: {e}")
            return jsonify({"error": str(e)}), 500

    def _load_existing_logger(session_id: str) -> DiagnosisLogger | None:
        """尝试从当天已保存的日志文件中加载 logger 状态。"""
        try:
            logs_dir = Path("logs/diagnosis")
            today_dir = logs_dir / datetime.now().strftime("%Y-%m-%d")
            if not today_dir.exists():
                return None
            for log_path in sorted(today_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if log_path.name.startswith(f"{session_id}_") and log_path.suffix == ".json":
                    try:
                        data = json.loads(log_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    restored = DiagnosisLogger(
                        session_id=data.get("session_id", session_id),
                        line_name=data.get("line_name", ""),
                        user_message=data.get("user_message", ""),
                    )
                    try:
                        restored.created_at = datetime.fromisoformat(data["created_at"])
                    except Exception:
                        pass
                    restored.stages = data.get("stages", [])
                    restored.events = data.get("events", [])
                    restored.tool_timings = data.get("tool_timings", [])
                    restored.frontend_output = data.get("frontend_output")
                    _active_loggers[session_id] = restored
                    return restored
        except Exception as e:
            logger.warning(f"加载已有诊断日志失败 {session_id}: {e}")
        return None

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------
    @app.route("/api/sessions", methods=["GET"])
    def list_sessions():
        """获取会话列表"""
        sessions = container.session_manager.list_sessions()
        result = []
        for s in sessions:
            voltage_level = ""
            fault_time = ""
            # 优先从会话的 fault_context 获取（创建时保存）
            if s.fault_context:
                voltage_level = s.fault_context.additional_info.get("voltage_level", "") or ""
                if s.fault_context.fault_time:
                    fault_time = s.fault_context.fault_time.isoformat()
            # 回退到 current_summary.fault_context（诊断完成后保存）
            elif s.current_summary and s.current_summary.fault_context:
                voltage_level = (
                    s.current_summary.fault_context.additional_info.get("voltage_level", "")
                    or ""
                )
                if s.current_summary.fault_context.fault_time:
                    fault_time = s.current_summary.fault_context.fault_time.isoformat()
            result.append(
                {
                    "session_id": s.session_id,
                    "line_name": s.line_name,
                    "status": s.status.value,
                    "voltage_level": voltage_level,
                    "fault_time": fault_time,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "action_log": [
                        {
                            "action_type": a.action_type,
                            "tool_name": a.parameters.get("tool_name", ""),
                            "description": a.parameters.get("description", ""),
                            "weight": a.parameters.get("weight"),
                            "timestamp": a.timestamp.isoformat(),
                        }
                        for a in s.action_log
                    ],
                }
            )
        return jsonify({"sessions": result})

    @app.route("/api/sessions/<id>/switch", methods=["POST"])
    def switch_session(id: str):
        """切换会话"""
        try:
            session = container.session_manager.switch_active(id)
            return jsonify(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/sessions/<id>/complete", methods=["POST"])
    def complete_session(id: str):
        """完成诊断，将会话标记为 completed"""
        try:
            session = container.session_manager.get(id)
            container.state_machine.transition(session, SessionStatus.COMPLETED)
            container.session_manager._persist()

            # 检查用户是否有调整操作，决定是否提示保存技能
            adjustment_types = {"exclude", "include", "adjust_weight", "modify_report", "recheck"}
            has_adjustments = any(
                a.action_type in adjustment_types for a in session.action_log
            )

            return jsonify(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                    "suggest_save_skill": has_adjustments,
                }
            )
        except Exception as e:
            logger.error(f"完成诊断失败: {e}")
            return jsonify({"error": str(e)}), 400

    @app.route("/api/reports", methods=["GET"])
    def list_reports():
        """获取所有诊断报告列表"""
        sessions = container.session_manager.list_sessions()
        reports = []
        for s in sessions:
            if not s.latest_report:
                continue
            fault_type = "未知"
            confidence = 0.0
            if s.current_summary and s.current_summary.primary_diagnosis:
                fault_type = s.current_summary.primary_diagnosis.fault_type
                confidence = s.current_summary.primary_diagnosis.confidence
            reports.append(
                {
                    "session_id": s.session_id,
                    "line_name": s.line_name,
                    "fault_type": fault_type,
                    "confidence": confidence,
                    "fault_time": (
                        s.fault_context.fault_time.isoformat()
                        if s.fault_context and s.fault_context.fault_time
                        else ""
                    ),
                    "created_at": s.created_at.isoformat(),
                    "report": s.latest_report,
                }
            )
        # 按创建时间倒序排列
        reports.sort(key=lambda r: r["created_at"], reverse=True)
        return jsonify({"reports": reports})

    @app.route("/api/tools", methods=["GET"])
    def list_tools():
        """获取诊断工具列表"""
        tools = container.tool_registry.list_tools()
        return jsonify(
            {
                "tools": [
                    {
                        "name": t.name,
                        "display_name": t.display_name,
                        "description": t.description,
                        "category": t.category,
                    }
                    for t in tools
                ]
            }
        )

    @app.route("/api/sessions/<id>", methods=["GET"])
    def get_session(id: str):
        """获取会话详情"""
        try:
            session = container.session_manager.get(id)
            # Build latest_summary from current_summary
            latest_summary = None
            if session.current_summary:
                primary = session.current_summary.primary_diagnosis
                latest_summary = {
                    "fault_type": primary.fault_type if primary else "未知",
                    "confidence": primary.confidence if primary else 0,
                    "report": session.latest_report,
                    "line_name": session.line_name,
                    "voltage_level": (
                        session.current_summary.fault_context.additional_info.get("voltage_level", "")
                        if session.current_summary.fault_context
                        and session.current_summary.fault_context.additional_info
                        else ""
                    ),
                }
            return jsonify(
                {
                    "session_id": session.session_id,
                    "line_name": session.line_name,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "active_weights": session.active_weights,
                    "excluded_tools": session.excluded_tools,
                    "rechecked_tools": session.rechecked_tools,
                    "latest_summary": latest_summary,
                    "chat_history": session.chat_history,
                    "action_log": [
                        {
                            "action_type": a.action_type,
                            "tool_name": a.parameters.get("tool_name", ""),
                            "description": a.parameters.get("description", ""),
                            "weight": a.parameters.get("weight"),
                            "timestamp": a.timestamp.isoformat(),
                        }
                        for a in session.action_log
                    ],
                    "summaries": [
                        {
                            "version": s.version,
                            "primary_diagnosis": (
                                s.primary_diagnosis.fault_type
                                if s.primary_diagnosis
                                else None
                            ),
                            "confidence": (
                                s.primary_diagnosis.confidence
                                if s.primary_diagnosis
                                else 0
                            ),
                            "created_at": s.created_at.isoformat(),
                        }
                        for s in session.summaries
                    ],
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    # ------------------------------------------------------------------
    # 模板管理 API
    # ------------------------------------------------------------------
    @app.route("/api/templates", methods=["GET"])
    def list_templates():
        """获取模板列表"""
        registry = container.template_registry
        return jsonify({"templates": registry.list_templates()})

    @app.route("/api/templates/upload", methods=["POST"])
    def upload_template():
        """上传模板文件"""
        if "file" not in request.files:
            return jsonify({"error": "缺少文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "文件名为空"}), 400

        allowed = {".md", ".docx", ".pdf"}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            return jsonify({"error": f"不支持的格式: {ext}"}), 400

        temp_path = None
        try:
            temp_path = Path("/tmp") / file.filename
            file.save(temp_path)

            registry = container.template_registry
            result = registry.upload(temp_path, file.filename)
            return jsonify({"success": True, "template": result})
        except Exception as e:
            logger.error(f"上传模板失败: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    @app.route("/api/templates/activate", methods=["POST"])
    def activate_template():
        """激活指定模板"""
        data = request.json or {}
        name = data.get("template_name", "").strip()

        if not name:
            return jsonify({"error": "模板名称不能为空"}), 400

        registry = container.template_registry
        success = registry.activate(name)
        if not success:
            return jsonify({"error": f"模板 '{name}' 不存在或解析失败"}), 404

        # 更新当前会话
        session = container.session_manager.get_active()
        if session:
            session.active_template_name = name
            container.session_manager._persist()

        return jsonify({"success": True, "active_template": name})

    @app.route("/api/templates/<name>", methods=["DELETE"])
    def delete_template(name: str):
        """删除模板"""
        registry = container.template_registry
        if registry.delete(name):
            return jsonify({"success": True, "message": f"模板 '{name}' 已删除"})
        return jsonify({"error": f"模板 '{name}' 不存在"}), 404

    @app.route("/api/templates/<name>/parsed", methods=["GET"])
    def get_template_parsed(name: str):
        """获取解析后的模板内容"""
        registry = container.template_registry
        content = registry.get_parsed_content(name)
        if content is None:
            return jsonify({"error": f"模板 '{name}' 未解析"}), 404
        return jsonify({"name": name, "content": content})

    @app.route("/api/health", methods=["GET"])
    def health():
        """健康检查"""
        return jsonify({"status": "ok", "version": "0.2.0"})

    @app.route("/api/sessions/clear", methods=["POST"])
    def clear_sessions():
        """清空所有会话"""
        try:
            sessions = container.session_manager.list_sessions()
            count = len(sessions)
            for session in sessions:
                container.session_manager._sessions.pop(session.session_id, None)
            container.session_manager._active_session_id = None
            container.session_manager._persist()
            return jsonify({"success": True, "message": f"已清空 {count} 个会话"})
        except Exception as e:
            logger.error(f"清空会话失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        """获取系统设置"""
        from src.core.models import DEFAULT_WEIGHTS

        return jsonify(
            {
                "default_weights": DEFAULT_WEIGHTS,
                "weight_range": {
                    "min": container.config.diagnosis.weight_min,
                    "max": container.config.diagnosis.weight_max,
                },
                "llm": {
                    "provider": container.config.llm.provider,
                    "model": container.config.llm.model,
                },
            }
        )

    @app.route("/api/settings/weights", methods=["POST"])
    def update_settings_weights():
        """更新默认权重配置"""
        data = request.json or {}
        weights = data.get("weights", {})

        if not weights:
            return jsonify({"error": "weights 不能为空"}), 400

        try:
            # 更新当前活跃会话的权重
            session = container.session_manager.get_active()
            if session:
                container.session_manager.update_weights(session.session_id, weights)
                return jsonify(
                    {
                        "success": True,
                        "message": "权重已更新",
                        "weights": session.active_weights,
                    }
                )
            return jsonify({"error": "没有活跃的会话"}), 400
        except Exception as e:
            logger.error(f"更新权重失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 技能管理 API（Markdown 格式）
    # ------------------------------------------------------------------
    DEFAULT_SKILL_NAME = "comprehensive_diagnosis"

    @app.route("/api/skills", methods=["GET"])
    def list_skills():
        """获取所有技能文件（隐藏 report_modifier — 运行时内部技能，不用于诊断策略）"""
        skill_names = container.skill_loader.list_skills()
        skills = []
        for name in skill_names:
            try:
                # report_modifier 是运行时报告修改技能，不在策略管理面板展示
                if name == "report_modifier":
                    continue

                content, _ = container.skill_loader.load(name)
                # 解析第一行标题作为描述
                description = ""
                for line in content.splitlines():
                    if line.startswith("# "):
                        description = line[2:].strip()
                        break
                skills.append(
                    {
                        "name": name,
                        "description": description,
                        "is_default": name == DEFAULT_SKILL_NAME,
                        "source": "系统" if name == DEFAULT_SKILL_NAME else "用户自定义",
                    }
                )
            except Exception as e:
                logger.warning(f"读取技能文件失败 {name}: {e}")
        return jsonify({"skills": skills})

    @app.route("/api/skills", methods=["POST"])
    def create_skill():
        """创建新技能文件"""
        data = request.get_json(force=True) or {}
        name = data.get("name", "").strip()
        content = data.get("content", "").strip()

        if not name:
            return jsonify({"error": "技能名称不能为空"}), 400
        if not content:
            return jsonify({"error": "技能内容不能为空"}), 400

        try:
            container.skill_loader.save(name, content)
            return jsonify(
                {
                    "success": True,
                    "message": f"技能 '{name}' 已保存",
                    "name": name,
                }
            )
        except Exception as e:
            logger.error(f"保存技能失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/<name>/activate", methods=["POST"])
    def activate_skill(name: str):
        """激活技能到当前会话"""
        session = container.session_manager.get_active()
        if not session:
            return jsonify({"error": "没有活跃的会话"}), 400

        skill_names = container.skill_loader.list_skills()
        if name not in skill_names:
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404

        try:
            session.active_skill_name = name
            return jsonify(
                {
                    "success": True,
                    "skill_name": name,
                    "message": f"技能 '{name}' 已激活",
                }
            )
        except Exception as e:
            logger.error(f"激活技能失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/<name>", methods=["DELETE"])
    def delete_skill(name: str):
        """删除技能（默认技能不可删除）"""
        if name == DEFAULT_SKILL_NAME:
            return jsonify({"error": f"默认技能 '{name}' 不可删除"}), 403
        if not container.skill_loader.delete(name):
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404
        return jsonify({"success": True, "message": f"技能 '{name}' 已删除"})

    @app.route("/api/skills/discover", methods=["POST"])
    def discover_tools():
        """手动触发工具扫描，返回新工具列表"""
        try:
            available_tools = container.tool_registry.list_tools()
            tool_names = [t.name for t in available_tools]
            return jsonify(
                {
                    "success": True,
                    "tools": tool_names,
                    "count": len(tool_names),
                }
            )
        except Exception as e:
            logger.error(f"工具扫描失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/skills/reset", methods=["POST"])
    def reset_skills():
        """重置当前会话为默认策略"""
        session = container.session_manager.get_active()
        if not session:
            return jsonify({"error": "没有活跃的会话"}), 400

        from src.core.models import DEFAULT_WEIGHTS

        container.session_manager.update_weights(
            session.session_id, DEFAULT_WEIGHTS.copy()
        )
        # 清空排除列表
        for tool in list(session.excluded_tools):
            container.session_manager.include_tool(session.session_id, tool)

        session.active_skill_name = None

        return jsonify(
            {
                "success": True,
                "message": "已重置为默认策略",
                "default_weights": DEFAULT_WEIGHTS,
            }
        )

    @app.route("/api/skills/default", methods=["GET"])
    def get_default_skill():
        """获取全局默认技能"""
        return jsonify({
            "default_skill": container.session_manager._default_skill_name,
            "available_skills": container.skill_loader.list_skills(),
        })

    @app.route("/api/skills/default", methods=["POST"])
    def set_default_skill():
        """设置全局默认技能"""
        data = request.json or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "技能名称不能为空"}), 400
        if name not in container.skill_loader.list_skills():
            return jsonify({"error": f"技能 '{name}' 不存在"}), 404
        container.session_manager.set_default_skill(name)
        container.session_manager._persist()
        return jsonify({"success": True, "default_skill": name})

    @app.route("/api/sessions/<id>/skill-summary", methods=["GET"])
    def generate_skill_summary(id: str):
        """生成技能摘要（基于会话操作历史，代码层构建完整 Agent Skill）"""
        try:
            session = container.session_manager.get(id)
        except Exception as e:
            return jsonify({"error": str(e)}), 404

        # 使用 SaveSkillCommand 的代码层构建逻辑生成完整 Skill
        from src.application.commands.save_skill import SaveSkillCommand

        cmd = SaveSkillCommand(
            llm_service=container.llm_service,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
            skill_loader=container.skill_loader,
            skills_dir=container.skill_loader._skills_dir,
        )
        config = cmd._build_skill_config(session, f"{session.line_name}_策略")
        content = cmd._build_skill_markdown(config)
        suggested_name = f"{session.line_name}_策略"
        return jsonify({"content": content, "suggested_name": suggested_name})

    # ------------------------------------------------------------------
    # 静态文件服务（前端 dist）
    # ------------------------------------------------------------------
    dist_dir = Path(os.getenv("FRONTEND_DIST", "web/dist")).resolve()

    if dist_dir.exists():

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path: str):
            """服务前端静态文件"""
            file_path = dist_dir / path
            if file_path.is_file():
                return send_from_directory(dist_dir, path)
            return send_from_directory(dist_dir, "index.html")

    return app


def _resolve_command(intent_type: IntentType, container):
    """根据意图类型解析对应的 Command 实例"""
    if intent_type == IntentType.DIAGNOSE:
        return DiagnoseCommand(
            tool_registry=container.tool_registry,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
            event_bus=container.event_bus,
            skill_loader=container.skill_loader,
            prompt_builder=container.prompt_builder,
            diagnosis_planner=container.diagnosis_planner,
            tool_executor=container.tool_executor,
            report_composer=container.report_composer,
        )
    elif intent_type == IntentType.EXCLUDE_TOOL:
        return ExcludeToolCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.INCLUDE_TOOL:
        return IncludeToolCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.RECHECK_TOOL:
        return RecheckToolCommand(
            tool_registry=container.tool_registry,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.ADJUST_WEIGHT:
        return AdjustWeightCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.SAVE_STRATEGY:
        from src.application.commands.save_skill import SaveSkillCommand
        return SaveSkillCommand(
            llm_service=container.llm_service,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
            skill_loader=container.skill_loader,
        )
    elif intent_type == IntentType.COMPLETE:
        return CompleteDiagnosisCommand(
            session_manager=container.session_manager,
            state_machine=container.state_machine,
        )
    elif intent_type == IntentType.MODIFY_REPORT:
        return ModifyReportCommand(
            llm_service=container.llm_service,
            session_manager=container.session_manager,
            state_machine=container.state_machine,
            skill_loader=container.skill_loader,
        )
    return None


def _sse_event(event: Event) -> str:
    """格式化 SSE 事件"""

    def _serialize(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serialize(v) for v in obj]
        return obj

    data = {
        "event_type": event.event_type.value,
        "session_id": event.session_id,
        "payload": _serialize(event.payload),
        "timestamp": event.timestamp.isoformat(),
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
