"""报告撰写器

通过单次 LLM 调用生成完整的诊断报告。
支持模板 Markdown 注入，由 LLM 自主按模板结构组织输出。
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.llm_service import LLMService
from src.domain.skill_loader import SkillLoader

logger = logging.getLogger(__name__)

DEFAULT_CHAPTERS = ["概述", "故障分析", "诊断证据", "诊断结论", "处理建议"]


class ReportComposer:
    """报告撰写器

    基于工具输出和模板配置，通过单次 LLM 调用生成完整诊断报告。
    纯 Skill 驱动：LLM 通过读取 Skill 自主计算加权置信度并排序。
    """

    def __init__(self, llm_service: LLMService, skill_loader: SkillLoader | None = None):
        self.llm = llm_service
        self.skill_loader = skill_loader

    async def compose(
        self,
        tool_outputs: Dict[str, ToolOutput],
        template: Optional[Any],  # 保留参数兼容，实际使用模板 Markdown
        session_id: str,
        fault_context: Optional[FaultContext] = None,
        action_log: Optional[list[dict]] = None,
        weights: Optional[Dict[str, float]] = None,
        active_template_name: Optional[str] = None,
        active_skill_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """撰写完整诊断报告。

        Args:
            tool_outputs: 各诊断工具的输出结果。
            template: 模板配置（向后兼容，优先使用 active_template_name）。
            session_id: 当前会话 ID。
            fault_context: 故障上下文。
            action_log: 用户操作历史。
            weights: 工具权重配置（传递给 LLM 作为参考，不代码计算）。
            active_template_name: 当前激活的模板名称。
            active_skill_name: 当前激活的技能名称（完整 skill 内容将加载到 prompt 中）。

        Returns:
            包含 summary 和 report 的字典。
        """
        # 加载模板 Markdown
        template_md = self._load_template_md(active_template_name)

        # 加载完整 skill 内容（自包含指令，LLM 从中读取所有规则）
        skill_md = ""
        if self.skill_loader and active_skill_name:
            skill_md, _ = self.skill_loader.load(active_skill_name)

        # 构建提示词
        prompt = self._build_prompt(
            tool_outputs, fault_context, action_log, weights, template_md, skill_md
        )

        messages = [
            {"role": "system", "content": "你是输电线路故障诊断报告撰写专家。"},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"会话 {session_id} 报告生成失败: {e}")
            raise

        formatted = self._format_response(response)
        summary = self._extract_summary(tool_outputs)
        if fault_context:
            summary["line_name"] = fault_context.line_name
            if fault_context.additional_info:
                summary["voltage_level"] = fault_context.additional_info.get("voltage_level", "")
            if fault_context.fault_time:
                summary["fault_time"] = fault_context.fault_time.isoformat()
        if action_log:
            summary["action_log"] = action_log

        return {"summary": summary, "report": formatted}

    def _load_template_md(self, template_name: Optional[str]) -> str:
        """加载激活模板的 Markdown 内容。"""
        if not template_name:
            return ""

        parsed_path = Path("templates/parsed") / f"{template_name}.md"
        if parsed_path.exists():
            return parsed_path.read_text(encoding="utf-8")

        # 回退：尝试直接读取 templates/ 下的 .md 文件
        direct_path = Path("templates") / f"{template_name}.md"
        if direct_path.exists():
            return direct_path.read_text(encoding="utf-8")

        logger.warning(f"模板文件不存在: {template_name}")
        return ""

    def _build_prompt(
        self,
        tool_outputs: Dict[str, ToolOutput],
        fault_context: Optional[FaultContext],
        action_log: Optional[list[dict]],
        weights: Optional[Dict[str, float]],
        template_md: str,
        skill_md: str = "",
    ) -> str:
        lines = [
            "请根据以下诊断工具输出，生成一份完整的输电线路故障诊断报告。",
            "",
        ]

        if fault_context:
            lines.extend(["## 诊断目标", ""])
            target_parts = []
            if fault_context.additional_info:
                voltage = fault_context.additional_info.get("voltage_level")
                if voltage:
                    target_parts.append(f"电压等级：{voltage}")
            target_parts.append(f"线路名称：{fault_context.line_name}")
            if fault_context.fault_time:
                target_parts.append(
                    f"故障时间：{fault_context.fault_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
                )
            target_parts.append("故障类型：跳闸")
            lines.append(" | ".join(target_parts))
            lines.append("")

        if weights:
            lines.extend([
                "## 工具权重配置",
                "",
                "请在诊断结论中按以下权重计算加权置信度：",
                "",
            ])
            for tool_name, weight in weights.items():
                lines.append(f"- {tool_name}: {weight}")
            lines.append("")

        if action_log:
            lines.extend(["## 用户操作历史", ""])
            for action in action_log:
                action_type = action.get("action_type", "")
                tool_name = action.get("tool_name", "")
                desc = action.get("description", "")
                if action_type == "exclude":
                    lines.append(f"- 排除 {tool_name} 诊断数据")
                elif action_type == "include":
                    lines.append(f"- 恢复 {tool_name} 诊断数据")
                elif action_type == "recheck":
                    lines.append(f"- 复查 {tool_name}")
                elif action_type == "adjust_weight":
                    w = action.get("weight", "")
                    lines.append(f"- 调整 {tool_name} 权重为 {w}")
                elif action_type == "modify_report":
                    lines.append(f"- 修改报告：{desc or tool_name}")
                elif action_type == "complete":
                    lines.append("- 完成诊断")
                else:
                    lines.append(f"- {action_type}: {desc or tool_name}")
            lines.append("")

        lines.extend(["## 诊断工具输出", ""])
        for tool_name, output in tool_outputs.items():
            lines.append(f"### {tool_name}")
            if output.raw_text:
                lines.append(f"原始文本：\n{output.raw_text}")
            if output.structured_data:
                lines.append(
                    f"结构化数据：\n```json\n"
                    f"{json.dumps(output.structured_data, ensure_ascii=False, indent=2)}"
                    f"\n```"
                )
            lines.append("")

        if template_md:
            lines.extend([
                "## 报告模板约束",
                "",
                "请严格按照以下模板章节结构组织报告：",
                "",
                template_md,
                "",
            ])
        else:
            lines.extend([
                "## 报告要求",
                "",
                "请生成包含以下章节的完整报告：",
                "",
            ])
            for chapter in DEFAULT_CHAPTERS:
                lines.append(f"- {chapter}")
            lines.append("")

        if skill_md:
            lines.extend([
                "## 诊断技能指南（必须遵循）",
                "",
                "以下技能指南包含诊断策略和报告撰写规则。请仔细阅读并严格遵循其中的所有指令：",
                "",
                skill_md,
                "",
            ])

        lines.extend([
            "格式要求：",
            "1. 每个章节使用 `## 章节名` 作为标题",
            "2. 内容专业、逻辑清晰",
            "3. 基于提供的诊断数据进行分析",
            "4. 使用 Markdown 格式输出",
            "5. 诊断结论中必须列出每个工具的加权置信度计算过程",
        ])

        return "\n".join(lines)

    def _format_response(self, response: str) -> str:
        stripped = response.strip()
        if not stripped.startswith("# "):
            return f"# 输电线路故障诊断报告\n\n{stripped}"
        return stripped

    def _extract_summary(
        self, tool_outputs: Dict[str, ToolOutput]
    ) -> Dict[str, Any]:
        """提取诊断摘要（纯工具输出，不做加权计算）。

        加权计算由 LLM 通过 Skill 自主完成。
        """
        best_tool = None
        best_confidence = 0.0
        best_fault_type = "未知"

        for tool_name, output in tool_outputs.items():
            structured = output.structured_data or {}
            confidence = structured.get("confidence", 0.0)
            fault_type = structured.get("fault_type", "未知")
            if not isinstance(confidence, (int, float)):
                continue

            if confidence > best_confidence:
                best_confidence = confidence
                best_fault_type = fault_type
                best_tool = tool_name

        return {
            "fault_type": best_fault_type,
            "confidence": round(best_confidence, 2),
            "primary_tool": best_tool or "unknown",
        }
