"""提示词构建器

组装完整的 LLM 提示词，包含技能指南、工具目录、会话覆盖和用户输入。
"""

from typing import List, Dict, Optional


class ToolConfig:
    """工具配置（简化定义，用于类型注解）"""

    def __init__(self, name: str, display_name: str, description: str) -> None:
        self.name = name
        self.display_name = display_name
        self.description = description


class DiagnosisSession:
    """诊断会话（简化定义，用于类型注解）"""

    def __init__(
        self,
        active_weights: Optional[Dict[str, float]] = None,
        excluded_tools: Optional[List[str]] = None,
        included_tools: Optional[List[str]] = None,
        tool_order: Optional[List[str]] = None,
    ) -> None:
        self.active_weights = active_weights or {}
        self.excluded_tools = excluded_tools or []
        self.included_tools = included_tools or []
        self.tool_order = tool_order


class PromptBuilder:
    """提示词构建器

    负责将技能指南、工具配置、会话状态和用户输入组装成完整的 LLM 提示词。
    """

    @staticmethod
    def build(
        skill_md: str,
        session: DiagnosisSession,
        tools: List[ToolConfig],
        user_message: str,
    ) -> str:
        """组装完整的 LLM 提示词。

        Args:
            skill_md: 技能指南 Markdown 内容。
            session: 当前诊断会话，包含权重、排除/包含工具等覆盖信息。
            tools: 可用工具配置列表。
            user_message: 用户输入消息。

        Returns:
            完整的提示词字符串，包含所有必要章节。
        """
        sections: List[str] = []

        # 1. 系统角色头
        sections.append("你是输电线路故障诊断专家。请严格遵循以下技能指南执行诊断。")

        # 2. 技能指南
        sections.append("\n## 技能指南\n")
        sections.append(skill_md)

        # 3. 可用工具目录
        sections.append("\n## 可用工具目录\n")
        if tools:
            for tool in tools:
                sections.append(
                    f"- **{tool.name}** ({tool.display_name}): {tool.description}"
                )
        else:
            sections.append("（暂无可用工具）")

        # 4. 当前会话覆盖
        overrides = PromptBuilder._build_overrides(session)
        if overrides:
            sections.append("\n## 当前会话调整\n")
            sections.append(overrides)

        # 5. 新工具通知
        new_tools = PromptBuilder._detect_new_tools(skill_md, tools)
        if new_tools:
            sections.append("\n## 新工具通知\n")
            sections.append("以下工具未在技能指南中提及，可根据需要调用：\n")
            for tool in new_tools:
                sections.append(
                    f"- **{tool.name}** ({tool.display_name}): {tool.description}"
                )

        # 6. 用户输入
        sections.append("\n## 用户输入\n")
        sections.append(user_message)

        # 7. 输出格式
        sections.append("\n## 输出格式\n")
        sections.append(
            "请严格按以下 JSON 格式输出诊断计划（不要添加 markdown 代码块标记）：\n"
        )
        sections.append(
            '{\n'
            '  "reasoning": "...",\n'
            '  "tools_to_call": [{"name": "...", "rationale": "...", "parallel": true}],\n'
            '  "report_structure": ["概述", "故障分析", ...]\n'
            '}'
        )

        return "\n".join(sections)

    @staticmethod
    def _build_overrides(session: DiagnosisSession) -> str:
        """构建会话调整的文本描述。

        Args:
            session: 当前诊断会话。

        Returns:
            会话调整的文本描述，若无调整则返回空字符串。
        """
        parts: List[str] = []

        if session.active_weights:
            parts.append("### 权重调整")
            for tool_name, weight in session.active_weights.items():
                parts.append(f"- {tool_name}: {weight}")

        if session.excluded_tools:
            parts.append("### 已排除工具（以下工具已被用户明确排除，诊断计划中禁止调用）")
            for tool_name in session.excluded_tools:
                parts.append(f"- {tool_name}")
            parts.append("注意：已排除的工具绝对不能出现在 tools_to_call 列表中。")

        if session.included_tools:
            parts.append("### 已包含工具")
            for tool_name in session.included_tools:
                parts.append(f"- {tool_name}")

        if session.tool_order:
            parts.append("### 工具调用顺序")
            parts.append(", ".join(session.tool_order))

        return "\n".join(parts)

    @staticmethod
    def _detect_new_tools(skill_md: str, tools: List[ToolConfig]) -> List[ToolConfig]:
        """检测技能指南中未提及的工具。

        Args:
            skill_md: 技能指南 Markdown 内容。
            tools: 可用工具配置列表。

        Returns:
            未在技能指南中提及的工具列表。
        """
        return [tool for tool in tools if tool.name not in skill_md]
