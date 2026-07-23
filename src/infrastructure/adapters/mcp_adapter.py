"""MCP 工具适配器 — HTTP 客户端模式"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)


class MCPToolAdapter(ToolAdapter):
    """MCP 工具适配器 — 通过 HTTP 调用独立 MCP 服务"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._name = config.get("tool_name", "unknown")
        self._display_name = config.get("display_name", self._name)
        self._description = config.get("description", "")
        self._category = config.get("category", "unknown")
        self.url = config.get("url", "")
        self.timeout = config.get("timeout", 30)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> str:
        return self._category

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def execute(self, context: FaultContext) -> ToolOutput:
        """调用 MCP 服务"""
        client = await self._get_client()

        # 支持 DiagnosisContext（嵌套 fault_context）和直接的 FaultContext
        fault_ctx = getattr(context, "fault_context", None) or context
        fault_time = getattr(fault_ctx, "fault_time", None)
        additional_info = getattr(fault_ctx, "additional_info", {}) or {}

        payload = {
            "line_name": getattr(fault_ctx, "line_name", getattr(context, "line_name", "")),
            "voltage_level": additional_info.get("voltage_level") if isinstance(additional_info, dict) else None,
            "fault_time": fault_time.isoformat() if fault_time else None,
            "additional_info": {
                "line_id": getattr(fault_ctx, "line_id", None),
                "tower_id": getattr(fault_ctx, "tower_id", None),
                "weather_info": getattr(fault_ctx, "weather_info", None),
                "scada_data": getattr(fault_ctx, "scada_data", None),
                "wave_data": getattr(fault_ctx, "wave_data", None),
                "images": getattr(fault_ctx, "images", None),
                **(additional_info if isinstance(additional_info, dict) else {}),
            },
        }

        try:
            response = await client.post(
                f"{self.url}/diagnose",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            tool_output = ToolOutput(
                tool_name=self.name,
                raw_text=data.get("raw_text", ""),
                structured_data=data.get("structured_data", {}),
                metadata=data.get("metadata", {}),
            )
            self._save_tool_output(tool_output, payload)
            return tool_output
        except httpx.HTTPError as e:
            logger.error(f"MCP 服务调用失败 {self.name}: {e}")
            return ToolOutput(
                tool_name=self.name,
                raw_text=f"工具调用失败: {e}",
                structured_data={"error": str(e), "fault_type": "未知", "confidence": 0.0},
                metadata={"error": True},
            )

    def _resolve_service_dir(self) -> str | None:
        """根据适配器配置的 URL 端口反查 mcp-services 下的服务目录名。

        Returns:
            服务目录名（如 "lightning-service"），未找到则返回 None。
        """
        match = re.search(r":(\d+)", self.url)
        if not match:
            return None
        port = int(match.group(1))

        repo_root = Path(__file__).resolve().parents[3]
        services_dir = repo_root / "mcp-services"
        if not services_dir.is_dir():
            return None

        for service_dir in services_dir.iterdir():
            if not service_dir.is_dir() or not service_dir.name.endswith("-service"):
                continue
            main_file = service_dir / "main.py"
            if not main_file.exists():
                continue
            try:
                text = main_file.read_text(encoding="utf-8")
            except Exception:
                continue
            env_match = re.search(
                r'os\.environ\.get\(\s*["\']PORT["\']\s*,\s*["\']?(\d+)["\']?\s*\)',
                text,
            )
            run_match = re.search(r'uvicorn\.run\([^)]*port\s*=\s*(\d+)', text)
            service_port = None
            if env_match:
                service_port = int(env_match.group(1))
            elif run_match:
                service_port = int(run_match.group(1))
            if service_port == port:
                return service_dir.name
        return None

    def _save_tool_output(
        self,
        tool_output: ToolOutput,
        payload: Dict[str, Any],
    ) -> None:
        """将 MCP 工具调用结果覆盖写入 mcp-services 下对应的 md 文件。

        每次调用覆盖原文件，仅保留最新一次记录。写入失败不影响主业务流程。

        Args:
            tool_output: 工具输出对象。
            payload: 本次调用的请求体。
        """
        service_dir = self._resolve_service_dir()
        if service_dir is None:
            logger.warning(f"无法为 {self.name} 解析服务目录，跳过调用记录保存")
            return

        repo_root = Path(__file__).resolve().parents[3]
        log_path = repo_root / "mcp-services" / f"{service_dir}.md"

        beijing_tz = timezone(timedelta(hours=8))
        timestamp = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        structured_data = tool_output.structured_data or {}
        metadata = tool_output.metadata or {}

        lines = [
            f"## 调用记录 — {timestamp}",
            "",
            "### 请求",
            "",
            "```json",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "```",
            "",
            "### 响应",
            "",
            "#### raw_text",
            "",
            tool_output.raw_text or "（空）",
            "",
            "#### structured_data",
            "",
            "```json",
            json.dumps(structured_data, ensure_ascii=False, indent=2),
            "```",
            "",
            "#### metadata",
            "",
            "```json",
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "```",
            "",
            "---",
            "",
        ]

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            logger.warning(f"保存 {self.name} 调用记录到 {log_path} 失败: {e}")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
