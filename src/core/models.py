from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class SessionStatus(str, Enum):
    """会话状态"""
    PENDING = "pending"
    DIAGNOSING = "diagnosing"
    MODIFYING = "modifying"
    COMPLETED = "completed"
    EXCLUDED = "excluded"
    RECHECKING = "rechecking"


class ConfidenceLevel(str, Enum):
    """置信度等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntentType(str, Enum):
    """意图类型"""
    DIAGNOSE = "diagnose"
    EXCLUDE_TOOL = "exclude_tool"
    INCLUDE_TOOL = "include_tool"
    RECHECK_TOOL = "recheck_tool"
    ADJUST_WEIGHT = "adjust_weight"
    MODIFY_REPORT = "modify_report"
    COMPLETE = "complete"
    LIST_SESSIONS = "list_sessions"
    SWITCH_SESSION = "switch_session"
    SAVE_STRATEGY = "save_strategy"
    LOAD_STRATEGY = "load_strategy"
    GENERAL = "general"


class EventType(str, Enum):
    """SSE 事件类型"""
    START = "start"
    THINKING = "thinking"
    RESULT = "result"
    CONTENT = "content"
    REPORT_CHUNK = "report_chunk"
    COMPLETE = "complete"
    ERROR = "error"
    STATUS = "status"


class RenderMode(str, Enum):
    """报告章节渲染模式"""
    TABLE = "table"
    TEXT = "text"
    MIXED = "mixed"


class AdapterType(str, Enum):
    """工具适配器类型"""
    MCP = "mcp"
    WEB_SCRAPER = "web_scraper"
    API = "api"
    CUSTOM = "custom"


# ============================================================================
# Tool & Adapter Models
# ============================================================================

class ToolOutput(BaseModel):
    """工具输出统一包装"""
    tool_name: str
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolConfig(BaseModel):
    """工具配置（从 YAML 加载）"""
    name: str
    display_name: str
    description: str
    category: str
    adapter: AdapterConfig
    output_schema: Optional[OutputSchemaConfig] = None
    report_mapping: Optional[ReportMappingConfig] = None


class AdapterConfig(BaseModel):
    """适配器配置"""
    type: AdapterType
    config: Dict[str, Any] = Field(default_factory=dict)


class OutputSchemaConfig(BaseModel):
    """输出模式配置"""
    type: str
    fields: Optional[List[FieldConfig]] = None


class FieldConfig(BaseModel):
    """字段配置"""
    name: str
    type: str
    description: str


class ReportMappingConfig(BaseModel):
    """报告映射配置"""
    chapter: str
    render_template: str


# ============================================================================
# Fault Context
# ============================================================================

class FaultContext(BaseModel):
    """故障上下文"""
    line_id: str
    line_name: str
    tower_id: Optional[str] = None
    fault_time: Optional[datetime] = None
    weather_info: Optional[Dict[str, Any]] = None
    scada_data: Optional[Dict[str, Any]] = None
    wave_data: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    additional_info: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Diagnosis Results
# ============================================================================

class DiagnosisResult(BaseModel):
    """单次诊断结果"""
    fault_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    evidence: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
    tool_name: str
    timestamp: datetime = Field(default_factory=datetime.now)


class DiagnosisSummary(BaseModel):
    """诊断摘要（一次完整诊断的版本）"""
    version: int = 1
    parent_version: Optional[int] = None
    fault_context: Optional[FaultContext] = None
    results: List[DiagnosisResult] = Field(default_factory=list)
    primary_diagnosis: Optional[DiagnosisResult] = None
    all_evidence: List[str] = Field(default_factory=list)
    confidence_distribution: Dict[str, float] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)
    weighted_scores: Dict[str, Any] = Field(default_factory=dict)
    excluded_tools: List[str] = Field(default_factory=list)
    rechecked_tools: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Session
# ============================================================================

class UserAction(BaseModel):
    """用户操作记录"""
    action_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


DEFAULT_WEIGHTS: Dict[str, float] = {
    "LightningDiagnosisTool": 1.0,
    "IcingDiagnosisTool": 0.9,
    "WindDiagnosisTool": 1.0,
    "WeatherDiagnosisTool": 1.0,
}


class DiagnosisSession(BaseModel):
    """诊断会话"""
    session_id: str
    line_name: str
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    active_weights: Dict[str, float] = Field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    excluded_tools: List[str] = Field(default_factory=list)
    rechecked_tools: List[str] = Field(default_factory=list)

    included_tools: List[str] = Field(default_factory=list)
    report_overrides: Dict[str, Any] = Field(default_factory=dict)
    tool_order: Optional[List[str]] = None
    active_skill_name: Optional[str] = None
    active_template_name: Optional[str] = None

    summaries: List[DiagnosisSummary] = Field(default_factory=list)
    current_summary: Optional[DiagnosisSummary] = None
    fault_context: Optional[FaultContext] = None
    action_log: List[UserAction] = Field(default_factory=list)
    latest_report: Optional[str] = None
    custom_strategy_name: Optional[str] = None
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    history_relation_cache: Optional[List[Dict[str, str]]] = None
    tool_outputs_cache: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        """确保权重是独立副本"""
        if self.active_weights is None or self.active_weights == {}:
            self.active_weights = DEFAULT_WEIGHTS.copy()


# ============================================================================
# Intent
# ============================================================================

class Intent(BaseModel):
    """意图识别结果"""
    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    raw_message: str = ""


# ============================================================================
# Event
# ============================================================================

class Event(BaseModel):
    """SSE 事件"""
    session_id: str
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

    @classmethod
    def start(cls, session_id: str, message: str | dict = "开始处理...") -> Event:
        payload = message if isinstance(message, dict) else {"message": message}
        return cls(session_id=session_id, event_type=EventType.START, payload=payload)

    @classmethod
    def thinking(cls, session_id: str, message: str) -> Event:
        return cls(session_id=session_id, event_type=EventType.THINKING, payload={"message": message})

    @classmethod
    def result(cls, session_id: str, data: Dict[str, Any]) -> Event:
        return cls(session_id=session_id, event_type=EventType.RESULT, payload=data)

    @classmethod
    def content(cls, session_id: str, text: str) -> Event:
        return cls(session_id=session_id, event_type=EventType.CONTENT, payload={"text": text})

    @classmethod
    def report_chunk(cls, session_id: str, text: str) -> Event:
        """报告流式增量块（payload.content 与前端累积逻辑约定一致）"""
        return cls(session_id=session_id, event_type=EventType.REPORT_CHUNK, payload={"content": text})

    @classmethod
    def complete(cls, session_id: str, data: Dict[str, Any]) -> Event:
        return cls(session_id=session_id, event_type=EventType.COMPLETE, payload=data)

    @classmethod
    def error(cls, session_id: str, message: str, code: Optional[str] = None) -> Event:
        return cls(
            session_id=session_id,
            event_type=EventType.ERROR,
            payload={"message": message, "code": code},
        )

    @classmethod
    def status(cls, session_id: str, data: dict) -> Event:
        return cls(session_id=session_id, event_type=EventType.STATUS, payload=data)


# ============================================================================
# Strategy / Skill
# ============================================================================

class Strategy(BaseModel):
    """诊断策略"""
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    tool_weights: Dict[str, float] = Field(default_factory=dict)
    excluded_tools: List[str] = Field(default_factory=list)

    template_name: Optional[str] = None
    chapter_order: Optional[List[str]] = None


# ============================================================================
# Report Template
# ============================================================================

class ChapterConfig(BaseModel):
    """报告章节配置"""
    chapter_type: str
    title: str
    required: bool = True
    render_mode: RenderMode = RenderMode.MIXED
    data_sources: List[str] = Field(default_factory=list)


class TemplateConfig(BaseModel):
    """模板配置"""
    name: str
    source_file: Optional[str] = None
    chapters: List[ChapterConfig] = Field(default_factory=list)
    default_weights: Dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Application Context
# ============================================================================

class DiagnosisContext(BaseModel):
    """诊断上下文（单次操作的数据边界）"""
    session_id: str
    line_name: str
    weights: Dict[str, float] = Field(default_factory=dict)
    excluded_tools: List[str] = Field(default_factory=list)
    rechecked_tools: List[str] = Field(default_factory=list)
    fault_context: Optional[FaultContext] = None


class ExecutionContext(BaseModel):
    """执行上下文（Command 接收的完整上下文）"""
    session: DiagnosisSession
    diagnosis_ctx: DiagnosisContext
    user_message: str
    intent: Optional[Intent] = None
    diagnosis_logger: Optional[Any] = None
