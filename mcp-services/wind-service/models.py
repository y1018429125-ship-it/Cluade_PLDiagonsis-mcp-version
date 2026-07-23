from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    line_name: str
    voltage_level: Optional[str] = None
    fault_time: Optional[datetime] = None
    additional_info: dict = Field(default_factory=dict)


class DiagnoseResponse(BaseModel):
    tool_name: str
    raw_text: str
    structured_data: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
