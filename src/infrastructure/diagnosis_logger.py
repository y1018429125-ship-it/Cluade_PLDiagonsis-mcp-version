"""诊断全流程日志记录器

每次前端提问时记录：
- 前端完整输出（最终 messages 列表）
- PLD 智能体回答问题的全流程细分时延
- SSE 事件流
- 各诊断工具调用耗时

日志按日期分目录，按会话写入 JSON 文件。
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiagnosisLogger:
    """诊断全流程日志记录器。"""

    def __init__(
        self,
        session_id: str,
        line_name: str,
        user_message: str,
        logs_dir: Optional[str] = None,
    ):
        self.session_id = session_id
        self.line_name = line_name
        self.user_message = user_message
        self.created_at = datetime.now(timezone.utc)
        self.logs_dir = Path(logs_dir or "logs/diagnosis").resolve()

        self.stages: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.tool_timings: List[Dict[str, Any]] = []
        self.frontend_output: Optional[List[Dict[str, Any]]] = None

        self._current_stage: Optional[Dict[str, Any]] = None

    def start_stage(self, stage_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """开始一个阶段计时。"""
        self._current_stage = {
            "stage": stage_name,
            "start_at": datetime.now(timezone.utc).isoformat(),
            "start_perf": time.perf_counter(),
            "details": details or {},
        }

    def end_stage(self, stage_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """结束当前阶段计时。"""
        if self._current_stage is None:
            logger.warning(f"结束阶段 {stage_name} 时没有找到正在进行的阶段")
            return

        if self._current_stage["stage"] != stage_name:
            logger.warning(
                f"阶段名称不匹配: 当前={self._current_stage['stage']}, 请求结束={stage_name}"
            )

        end_perf = time.perf_counter()
        duration_ms = round((end_perf - self._current_stage["start_perf"]) * 1000, 2)

        stage_record = {
            "stage": self._current_stage["stage"],
            "start_at": self._current_stage["start_at"],
            "end_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "details": {**self._current_stage.get("details", {}), **(details or {})},
        }
        self.stages.append(stage_record)
        self._current_stage = None

    def record_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """记录一个 SSE 事件。

        优化：
        - thinking 事件：连续的累计前缀消息（后一条以前一条为前缀）合并为一条，
          只保留最终的完整文本，避免 O(n^2) 重复记录。
        - result 事件：工具输出中的 base64 图片替换为占位符，避免日志体积膨胀。
        """
        payload = payload or {}
        if event_type == "result":
            payload = self._strip_images(payload)
        if (
            event_type == "thinking"
            and self.events
            and self.events[-1]["event_type"] == "thinking"
        ):
            prev_msg = self.events[-1]["payload"].get("message", "")
            new_msg = payload.get("message", "")
            if prev_msg and new_msg.startswith(prev_msg):
                self.events[-1]["payload"] = payload
                self.events[-1]["timestamp"] = datetime.now(timezone.utc).isoformat()
                return
        # report_chunk 为增量 delta：连续块拼接合并为一条，防止日志膨胀
        if (
            event_type == "report_chunk"
            and self.events
            and self.events[-1]["event_type"] == "report_chunk"
        ):
            prev = self.events[-1]["payload"].get("content", "")
            self.events[-1]["payload"]["content"] = prev + payload.get("content", "")
            self.events[-1]["timestamp"] = datetime.now(timezone.utc).isoformat()
            return
        self.events.append({
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        })

    @staticmethod
    def _strip_images(payload: Dict[str, Any]) -> Dict[str, Any]:
        """将 result 事件 payload 中的 base64 图片列表替换为占位符。"""
        details = (
            payload.get("output", {})
            .get("structured_data", {})
            .get("details", {})
        )
        images = details.get("images")
        if isinstance(images, list) and images:
            details["images"] = f"<已省略 {len(images)} 张图片，base64 未记录>"
        return payload

    def record_tool_timing(
        self,
        tool_name: str,
        start_perf: float,
        end_perf: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """记录工具调用耗时。

        Args:
            tool_name: 工具名称。
            start_perf: 调用者传入的 time.perf_counter() 起始值（仅用于计算时长）。
            end_perf: 调用者传入的 time.perf_counter() 结束值，未提供则取当前值。
            success: 是否成功。
            error: 错误信息（失败时）。

        Note:
            start_perf/end_perf 是相对计时器，不能转换为 wall-clock 时间戳。
            本方法使用调用时刻的 datetime.now() 作为 start_at/end_at，保证时间字段物理意义正确。
        """
        now = datetime.now(timezone.utc)
        if end_perf is None:
            end_perf = time.perf_counter()
        duration_ms = round((end_perf - start_perf) * 1000, 2)
        self.tool_timings.append({
            "tool_name": tool_name,
            "start_at": now.isoformat(),
            "end_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
        })

    def set_frontend_output(self, messages: List[Dict[str, Any]]) -> None:
        """设置前端完整输出（messages 列表）。"""
        self.frontend_output = messages

    def merge_frontend_log(self, frontend_log: Dict[str, Any]) -> None:
        """合并前端传来的日志数据。

        Args:
            frontend_log: 前端日志字典，通常包含 messages、timeline 等字段。
        """
        if not isinstance(frontend_log, dict):
            logger.warning("前端日志格式错误，跳过合并")
            return

        # 优先使用前端提供的完整 messages 作为前端输出
        messages = frontend_log.get("messages")
        if messages is not None:
            self.frontend_output = messages

        # 保存前端时间线（如果提供）
        timeline = frontend_log.get("timeline")
        if timeline is not None:
            self.events.append({
                "event_type": "frontend_timeline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": timeline,
            })

    def finalize(self) -> Optional[Path]:
        """持久化日志到文件。

        Returns:
            写入的文件路径，失败返回 None。
        """
        try:
            # 如果有未结束的阶段，先强制结束
            if self._current_stage is not None:
                self.end_stage(self._current_stage["stage"])

            date_dir = self.logs_dir / self.created_at.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            filename = (
                f"{self.session_id}_{self.created_at.strftime('%H%M%S%f')[:-3]}.json"
            )
            log_path = date_dir / filename

            log_data = {
                "session_id": self.session_id,
                "line_name": self.line_name,
                "user_message": self.user_message,
                "created_at": self.created_at.isoformat(),
                "finalized_at": datetime.now(timezone.utc).isoformat(),
                "frontend_output": self.frontend_output,
                "stages": self.stages,
                "events": self.events,
                "tool_timings": self.tool_timings,
            }

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)

            logger.info(f"诊断日志已保存: {log_path}")
            return log_path
        except Exception as e:
            logger.error(f"保存诊断日志失败: {e}")
            return None
