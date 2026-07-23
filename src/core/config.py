from typing import Any, Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM 配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = Field(default="", description="API Key")
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.3
    max_tokens: int = 4096


class IntentConfig(BaseSettings):
    """意图识别配置"""
    model_config = SettingsConfigDict(env_prefix="INTENT_", extra="ignore")

    confidence_threshold: float = 0.7
    fallback_intent: str = "general"


class DiagnosisConfig(BaseSettings):
    """诊断配置"""
    model_config = SettingsConfigDict(env_prefix="DIAGNOSIS_", extra="ignore")

    default_weights: Dict[str, float] = Field(default_factory=dict)
    weight_min: float = 0.1
    weight_max: float = 2.0
    weight_step: float = 0.3
    tool_timeout: int = 30


class ReportConfig(BaseSettings):
    """报告配置"""
    model_config = SettingsConfigDict(env_prefix="REPORT_", extra="ignore")

    templates_directory: str = "templates"
    default_template: str = "standard_report.docx"
    chapter_types: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class SessionConfig(BaseSettings):
    """会话配置"""
    model_config = SettingsConfigDict(env_prefix="SESSION_", extra="ignore")

    max_sessions_per_user: int = 20
    session_ttl_hours: int = 48
    auto_cleanup: bool = True


class ToolsConfig(BaseSettings):
    """工具配置"""
    model_config = SettingsConfigDict(env_prefix="TOOLS_", extra="ignore")

    config_directory: str = "config/tools"
    auto_load: bool = True


class AppConfig(BaseSettings):
    """应用总配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    intent: IntentConfig = Field(default_factory=IntentConfig)
    diagnosis: DiagnosisConfig = Field(default_factory=DiagnosisConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    debug: bool = False
    log_level: str = "INFO"
