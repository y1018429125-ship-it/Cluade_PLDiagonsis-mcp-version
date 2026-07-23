"""保存技能 Command

将当前会话的调整保存为符合 Agent Skill 规范的 Markdown 文件。
采用代码层直接构建（非 LLM 生成），基于 comprehensive_diagnosis.md 基线全文，
确保输出的 Skill 完全自包含，LLM 读取一个文件即可完整执行诊断流程。
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import yaml

from src.core.models import DiagnosisSession, Event, ExecutionContext
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.skill_loader import SkillLoader
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path("skills")
BASE_SKILL_NAME = "comprehensive_diagnosis"
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SaveSkillCommand(Command):
    """保存技能 Command

    代码层直接构建 Skill Markdown，确定性输出：
    1. 读取 comprehensive_diagnosis.md 基线正文
    2. 构建 YAML frontmatter（含 pushy description）
    3. 在工具策略表中标记排除工具为 SKIP
    4. 更新 weights YAML 代码块（如用户有调整）
    5. 追加个性化报告规则
    """

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skill_loader: SkillLoader,
        skills_dir: Path | None = None,
    ):
        self.llm = llm_service
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skill_loader = skill_loader
        self.skills_dir = skills_dir or DEFAULT_SKILLS_DIR

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行保存技能操作"""
        session = ctx.session
        skill_name = self._extract_skill_name(ctx)

        yield Event.thinking(
            session.session_id,
            f"保存技能: {skill_name}...",
        )

        self._validate_state(session)
        self._ensure_skills_dir()

        # 收集会话完整状态
        skill_config = self._build_skill_config(session, skill_name)

        # 代码层直接构建完整 Skill Markdown（不用 LLM）
        skill_md = self._build_skill_markdown(skill_config)

        file_path = self._save_to_file(skill_name, skill_md)

        session.active_skill_name = skill_name
        self.session_manager._persist()

        logger.info(f"技能已保存: {session.session_id} -> {file_path}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"技能 '{skill_name}' 已保存",
                "skill_name": skill_name,
                "file_path": str(file_path),
            },
        )

    def _extract_skill_name(self, ctx: ExecutionContext) -> str:
        if ctx.intent:
            name = ctx.intent.parameters.get("skill_name", "")
            if name:
                return name
            name = ctx.intent.parameters.get("strategy_name", "")
            if name:
                return name
        return f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _validate_state(self, session: DiagnosisSession) -> None:
        if not self.state_machine.can_execute(session, "save_strategy"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许保存技能"
            )

    def _ensure_skills_dir(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _build_skill_config(self, session: DiagnosisSession, name: str) -> dict:
        """收集会话状态构建 Skill 配置。"""
        weights = session.active_weights.copy()
        excluded = session.excluded_tools.copy()

        action_summary = []
        report_modifications = []
        for action in session.action_log:
            action_summary.append({
                "type": action.action_type,
                "params": action.parameters,
                "time": action.timestamp.isoformat(),
            })
            if action.action_type == "modify_report":
                instruction = action.parameters.get("instruction", "")
                if instruction:
                    report_modifications.append(instruction)

        return {
            "name": name,
            "line_context": session.line_name,
            "weights": weights,
            "excluded_tools": excluded,
            "template_name": session.active_template_name,
            "action_history": action_summary,
            "report_modifications": report_modifications,
        }

    # ------------------------------------------------------------------
    # 代码层直接构建 Skill Markdown
    # ------------------------------------------------------------------

    def _build_skill_markdown(self, config: dict) -> str:
        """代码层直接构建完整 Skill Markdown（确定性输出）。"""
        frontmatter = self._build_frontmatter(config)
        base_body = self._load_base_skill_body()
        body = self._mark_excluded_tools(base_body, config["excluded_tools"])
        body = self._update_weights(body, config["weights"])
        personalized = self._build_personalized_section(config)
        return f"{frontmatter}\n\n{body}\n\n{personalized}"

    def _build_frontmatter(self, config: dict) -> str:
        """构建 YAML frontmatter（pushy description）。"""
        line = config["line_context"] or "transmission lines"
        name = config["name"]
        return f"""---
name: {name}
description: |
  USE THIS SKILL when diagnosing power transmission line faults for {line}.
  ALWAYS activate when the input contains line name "{line}" combined with
  fault/trip/abnormal/flashover/ground/short-circuit keywords.
  Applies to 220kV/500kV/750kV/1000kV transmission lines.
  DO NOT use for distribution lines (below 110kV) or non-power-system diagnostics.
---"""

    def _load_base_skill_body(self) -> str:
        """读取 comprehensive_diagnosis.md，去掉 frontmatter，返回正文。"""
        base_path = self.skills_dir / f"{BASE_SKILL_NAME}.md"
        if not base_path.exists():
            logger.warning(f"基线技能文件不存在: {base_path}，返回空正文")
            return ""
        content = base_path.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(content)
        if match:
            return content[match.end():].strip()
        return content.strip()

    def _mark_excluded_tools(self, body: str, excluded: list[str]) -> str:
        """在工具调用策略表中标记排除的工具为 SKIP。"""
        for tool in excluded:
            # 匹配表格行：| LightningDiagnosisTool | 1.0 | Always call |
            # 需要处理可能有 ** 加粗的情况
            pattern = rf"(\|\s*\*?{re.escape(tool)}\*?\s*\|[^|]+\|)([^|]*)\|"
            replacement = rf"\1 **SKIP — excluded by user preference** |"
            body = re.sub(pattern, replacement, body)
        return body

    def _update_weights(self, body: str, weights: dict[str, float]) -> str:
        """更新正文中的 weights YAML 代码块。"""
        if not weights:
            return body
        # 找到 ```yaml\nweights:...``` 代码块并替换
        yaml_content = yaml.dump({"weights": weights}, allow_unicode=True).strip()
        pattern = r"```yaml\s*\nweights:.*?```"
        replacement = f"```yaml\n{yaml_content}\n```"
        body = re.sub(pattern, replacement, body, flags=re.DOTALL)
        return body

    def _build_personalized_section(self, config: dict) -> str:
        """构建个性化修改章节。"""
        sections: list[str] = []
        sections.append("# 基于本次诊断会话的个性化优化\n")

        # 排除工具
        if config["excluded_tools"]:
            sections.append("## 排除的工具\n")
            for tool in config["excluded_tools"]:
                sections.append(
                    f"- **SKIP {tool} entirely** — do not include it in the diagnosis plan or report."
                )
            sections.append("")

        # 权重调整
        weight_changes = []
        default_weights = self._load_default_weights()
        for tool, weight in config["weights"].items():
            default = default_weights.get(tool)
            if default is not None and float(weight) != float(default):
                weight_changes.append((tool, weight))

        if weight_changes:
            sections.append("## 权重调整\n")
            for tool, weight in weight_changes:
                sections.append(
                    f"- {tool}: use weight {weight} (override default {default_weights.get(tool, 'N/A')})"
                )
            sections.append("")

        # 报告修改规则
        report_rules = []
        for action in config["action_history"]:
            if action["type"] == "modify_report":
                instruction = action["params"].get("instruction", "")
                if instruction:
                    report_rules.append(instruction)

        if report_rules:
            sections.append("## 报告撰写规则（必须遵循）\n")
            sections.append(
                "When composing the report, apply the following rules IN ADDITION to the standard template structure:"
            )
            for rule in report_rules:
                sections.append(f"- **{rule}**")
            sections.append("")

        # 模板引用
        if config["template_name"]:
            sections.append("## 模板引用\n")
            sections.append(
                f"- Use template **{config['template_name']}** as the report structure guide."
            )
            sections.append("")

        sections.append(
            f"---\n\n*Generated from session on {config['line_context']}, {datetime.now().strftime('%Y-%m-%d')}*"
        )
        return "\n".join(sections)

    def _load_default_weights(self) -> dict[str, float]:
        """从基线 skill 加载默认权重。"""
        base_path = self.skills_dir / f"{BASE_SKILL_NAME}.md"
        if not base_path.exists():
            return {}
        content = base_path.read_text(encoding="utf-8")
        match = re.search(r"```yaml\s*(.*?)```", content, re.DOTALL)
        if match:
            try:
                config = yaml.safe_load(match.group(1))
                if isinstance(config, dict):
                    return config.get("weights", {})
            except yaml.YAMLError:
                pass
        return {}

    def _save_to_file(self, name: str, content: str) -> Path:
        file_path = self.skills_dir / f"{name}.md"
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.error(f"写入技能文件失败: {e}")
            raise InvalidStateError(f"无法保存技能文件: {e}") from e
        if hasattr(self.skill_loader, "_cache"):
            self.skill_loader._cache[name] = content
        return file_path
