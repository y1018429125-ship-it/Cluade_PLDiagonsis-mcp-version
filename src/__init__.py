"""PLDiagnosis - 统一导入根（Facade 模式）

所有模块统一从 src 根导入，禁止相对导入和跨级导入。
"""

from src.core.models import (
    AdapterConfig,
    AdapterType,
    ChapterConfig,
    ConfidenceLevel,
    DiagnosisContext,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisSummary,
    Event,
    EventType,
    ExecutionContext,
    FaultContext,
    FieldConfig,
    Intent,
    IntentType,
    OutputSchemaConfig,
    RenderMode,
    ReportMappingConfig,
    SessionStatus,
    Strategy,
    TemplateConfig,
    ToolConfig,
    ToolOutput,
    UserAction,
)

from src.core.config import AppConfig, DiagnosisConfig, IntentConfig, LLMConfig, ReportConfig, SessionConfig, ToolsConfig
from src.core.exceptions import (
    ConfigLoadError,
    InvalidStateError,
    LLMServiceError,
    MCPConnectionError,
    PLDiagnosisError,
    SessionNotFoundError,
    StrategyNotFoundError,
    TemplateParseError,
    ToolExecutionError,
    ToolNotFoundError,
    WeightValidationError,
)

from src.application.commands.base import Command
from src.application.commands.diagnose import DiagnoseCommand
from src.application.commands.exclude import ExcludeToolCommand
from src.application.commands.recheck import RecheckToolCommand
from src.application.commands.adjust_weight import AdjustWeightCommand
from src.application.commands.save_strategy import SaveStrategyCommand
from src.application.context import ContextBuilder

from src.domain.state_machine import StateMachine
from src.domain.session_manager import SessionManager
from src.domain.report_engine import ReportEngine
from src.domain.intent_classifier import IntentClassifier

from src.infrastructure.event_bus import EventBus
from src.infrastructure.llm_service import LLMService
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.template_parser import TemplateParser

from src.interfaces.web import create_app
from src.interfaces.dependency_injection import Container, get_container

__all__ = [
    # Models
    "AdapterConfig",
    "AdapterType",
    "ChapterConfig",
    "ConfidenceLevel",
    "DiagnosisContext",
    "DiagnosisResult",
    "DiagnosisSession",
    "DiagnosisSummary",
    "Event",
    "EventType",
    "ExecutionContext",
    "FaultContext",
    "FieldConfig",
    "Intent",
    "IntentType",
    "OutputSchemaConfig",
    "RenderMode",
    "ReportMappingConfig",
    "SessionStatus",
    "Strategy",
    "TemplateConfig",
    "ToolConfig",
    "ToolOutput",
    "UserAction",
    # Config
    "AppConfig",
    "DiagnosisConfig",
    "IntentConfig",
    "LLMConfig",
    "ReportConfig",
    "SessionConfig",
    "ToolsConfig",
    # Exceptions
    "ConfigLoadError",
    "InvalidStateError",
    "LLMServiceError",
    "MCPConnectionError",
    "PLDiagnosisError",
    "SessionNotFoundError",
    "StrategyNotFoundError",
    "TemplateParseError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "WeightValidationError",
    # Commands
    "Command",
    "DiagnoseCommand",
    "ExcludeToolCommand",
    "RecheckToolCommand",
    "AdjustWeightCommand",
    "SaveStrategyCommand",
    "ContextBuilder",
    # Domain
    "StateMachine",
    "SessionManager",
    "ReportEngine",
    "IntentClassifier",
    # Infrastructure
    "EventBus",
    "LLMService",
    "ToolRegistry",
    "TemplateParser",
    # Interfaces
    "create_app",
    "Container",
    "get_container",
]
