"""依赖注入容器

集中管理所有组件的依赖关系。
"""

from functools import lru_cache
from pathlib import Path

import yaml

from src.core.config import AppConfig, LLMConfig
from src.infrastructure.event_bus import EventBus
from src.infrastructure.llm_service import LLMService
from src.infrastructure.adapters.registry import ToolRegistry
from src.infrastructure.template_parser import TemplateParser
from src.infrastructure.session_repository import SessionRepository
from src.domain.state_machine import StateMachine
from src.domain.session_manager import SessionManager
from src.domain.intent_classifier import IntentClassifier
from src.domain.report_engine import ReportEngine
from src.domain.skill_loader import SkillLoader
from src.domain.prompt_builder import PromptBuilder
from src.domain.diagnosis_planner import DiagnosisPlanner
from src.domain.tool_executor import ToolExecutor
from src.domain.report_composer import ReportComposer
from src.domain.template_registry import TemplateRegistry


class Container:
    """依赖注入容器"""

    def __init__(self):
        self.config = AppConfig()
        self._merge_yaml_config()
        self.event_bus = EventBus()
        self.llm_service = LLMService(self.config.llm)
        self.tool_registry = ToolRegistry(self.config)
        self.state_machine = StateMachine(self.event_bus)
        self.session_repository = SessionRepository()
        self.session_manager = SessionManager(
            self.event_bus, self.state_machine, self.session_repository
        )
        self.intent_classifier = IntentClassifier(self.llm_service)
        self.report_engine = ReportEngine(self.llm_service, self.event_bus)
        self.template_parser = TemplateParser()
        self.skill_loader = SkillLoader()
        self.prompt_builder = PromptBuilder()
        self.diagnosis_planner = DiagnosisPlanner(self.llm_service)
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.template_registry = TemplateRegistry()
        self.report_composer = ReportComposer(self.llm_service, self.skill_loader)

    def _merge_yaml_config(self) -> None:
        """合并 config.yaml 中的配置（环境变量优先）"""
        yaml_path = Path("config/config.yaml")
        if not yaml_path.exists():
            return
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return
        if not data:
            return

        # 合并 llm 配置（环境变量优先，但 config.yaml 覆盖默认值）
        if "llm" in data:
            llm_data = data["llm"]
            for key, value in llm_data.items():
                # 仅当环境变量未提供时，使用 config.yaml 的值
                env_val = getattr(self.config.llm, key, None)
                if env_val is None or env_val == LLMConfig.model_fields[key].default:
                    if hasattr(self.config.llm, key):
                        setattr(self.config.llm, key, value)

        # 合并 report.chapter_types（仅当当前为空时）
        if "report" in data and "chapter_types" in data["report"]:
            if not self.config.report.chapter_types:
                self.config.report.chapter_types = data["report"]["chapter_types"]

        # 合并 diagnosis.default_weights（仅当当前为空时）
        if "diagnosis" in data and "default_weights" in data["diagnosis"]:
            if not self.config.diagnosis.default_weights:
                self.config.diagnosis.default_weights = data["diagnosis"]["default_weights"]

        # 合并 session 配置
        if "session" in data:
            for key, value in data["session"].items():
                if hasattr(self.config.session, key):
                    setattr(self.config.session, key, value)

        # 合并 tools 配置
        if "tools" in data:
            for key, value in data["tools"].items():
                if hasattr(self.config.tools, key):
                    setattr(self.config.tools, key, value)

    async def init(self) -> None:
        """初始化容器"""
        await self.tool_registry.load_tools()


@lru_cache()
def get_container() -> Container:
    """获取全局容器实例"""
    return Container()
