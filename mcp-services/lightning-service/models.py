"""Request/response models matching the PLDiagnosis MCP service contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    """Request model expected by PLDiagnosis MCPToolAdapter."""

    line_name: str
    voltage_level: Optional[str] = None
    fault_time: Optional[datetime] = None
    additional_info: Dict[str, Any] = Field(default_factory=dict)


class DiagnoseResponse(BaseModel):
    """Response model expected by PLDiagnosis MCPToolAdapter."""

    tool_name: str
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
