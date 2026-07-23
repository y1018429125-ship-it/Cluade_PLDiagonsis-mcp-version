"""报告引擎

模板驱动 + LLM 章节化生成。
"""

import logging
from typing import Dict, List, Optional

from src.core.models import (
    ChapterConfig,
    DiagnosisContext,
    DiagnosisSummary,
    Event,
    RenderMode,
    TemplateConfig,
    ToolOutput,
)

# 预置默认章节配置（当模板未上传或章节为空时使用）
DEFAULT_CHAPTERS: list[ChapterConfig] = [
    ChapterConfig(
        chapter_type="overview",
        title="概述",
        required=True,
        render_mode=RenderMode.TEXT,
    ),
    ChapterConfig(
        chapter_type="fault_analysis",
        title="故障分析",
        required=True,
        render_mode=RenderMode.MIXED,
    ),
    ChapterConfig(
        chapter_type="evidence",
        title="诊断证据",
        required=True,
        render_mode=RenderMode.TABLE,
        data_sources=[],
    ),
    ChapterConfig(
        chapter_type="conclusion",
        title="诊断结论",
        required=True,
        render_mode=RenderMode.TEXT,
    ),
    ChapterConfig(
        chapter_type="recommendation",
        title="处理建议",
        required=True,
        render_mode=RenderMode.TEXT,
    ),
]
from src.infrastructure.llm_service import LLMService
from src.infrastructure.event_bus import EventBus

logger = logging.getLogger(__name__)


class ReportEngine:
    """报告引擎"""

    def __init__(self, llm_service: LLMService, event_bus: EventBus):
        self.llm = llm_service
        self.event_bus = event_bus

    async def generate(
        self,
        summary: DiagnosisSummary,
        template: TemplateConfig,
        tool_outputs: Dict[str, ToolOutput],
        session_id: str,
    ) -> str:
        """生成诊断报告"""
        await self.event_bus.publish(
            Event.thinking(session_id, "正在生成诊断报告...")
        )

        chapters_content = []

        chapters = template.chapters if template.chapters else DEFAULT_CHAPTERS

        for chapter in chapters:
            content = await self._generate_chapter(
                chapter, summary, tool_outputs, session_id
            )
            chapters_content.append({
                "title": chapter.title,
                "type": chapter.chapter_type,
                "content": content,
            })

        # 组装完整报告
        report = self._assemble_report(chapters_content)

        await self.event_bus.publish(
            Event.complete(session_id, {"report": report, "chapters": len(chapters_content)})
        )

        return report

    async def _generate_chapter(
        self,
        chapter: ChapterConfig,
        summary: DiagnosisSummary,
        tool_outputs: Dict[str, ToolOutput],
        session_id: str,
    ) -> str:
        """生成单个章节"""
        # 筛选相关工具输出
        relevant_outputs = self._filter_relevant_outputs(
            chapter, tool_outputs, summary
        )

        # 根据渲染模式生成内容
        if chapter.render_mode == RenderMode.TABLE:
            return await self._render_table(chapter, relevant_outputs)
        elif chapter.render_mode == RenderMode.TEXT:
            return await self._render_text(chapter, relevant_outputs, summary)
        else:  # MIXED
            return await self._render_mixed(chapter, relevant_outputs, summary)

    def _filter_relevant_outputs(
        self,
        chapter: ChapterConfig,
        tool_outputs: Dict[str, ToolOutput],
        summary: DiagnosisSummary,
    ) -> Dict[str, ToolOutput]:
        """筛选与章节相关的工具输出"""
        if chapter.data_sources:
            return {
                name: output
                for name, output in tool_outputs.items()
                if name in chapter.data_sources
            }

        # 默认：诊断证据章节包含所有工具输出
        if chapter.chapter_type == "evidence":
            return tool_outputs

        # 其他章节根据内容判断
        return tool_outputs

    async def _render_table(
        self, chapter: ChapterConfig, outputs: Dict[str, ToolOutput]
    ) -> str:
        """表格渲染（结构化数据）"""
        lines = [f"## {chapter.title}\n"]

        for tool_name, output in outputs.items():
            if output.structured_data:
                lines.append(f"### {tool_name}")
                lines.append("| 字段 | 值 |")
                lines.append("|------|------|")
                for key, value in output.structured_data.items():
                    lines.append(f"| {key} | {value} |")
                lines.append("")
            elif output.raw_text:
                lines.append(f"### {tool_name}")
                lines.append(output.raw_text)
                lines.append("")

        return "\n".join(lines)

    async def _render_text(
        self,
        chapter: ChapterConfig,
        outputs: Dict[str, ToolOutput],
        summary: DiagnosisSummary,
    ) -> str:
        """文本渲染（LLM 生成）"""
        prompt = self._build_chapter_prompt(chapter, outputs, summary)
        messages = [{"role": "user", "content": prompt}]
        return await self.llm.chat(messages)

    async def _render_mixed(
        self,
        chapter: ChapterConfig,
        outputs: Dict[str, ToolOutput],
        summary: DiagnosisSummary,
    ) -> str:
        """混合渲染（表格 + LLM 分析）"""
        # 先渲染表格
        table_part = await self._render_table(chapter, outputs)

        # 再生成分析文字
        prompt = f"""基于以下诊断数据，为"{chapter.title}"章节写一段专业分析。

数据：
{self._outputs_to_text(outputs)}

要求：
1. 专业、简洁
2. 指出关键发现
3. 不超过300字
"""
        messages = [{"role": "user", "content": prompt}]
        analysis = await self.llm.chat(messages)

        return f"{table_part}\n\n### 分析\n{analysis}"

    def _build_chapter_prompt(
        self,
        chapter: ChapterConfig,
        outputs: Dict[str, ToolOutput],
        summary: DiagnosisSummary,
    ) -> str:
        """构建章节生成提示"""
        return f"""请为诊断报告生成"{chapter.title}"章节。

故障线路：{summary.fault_context.line_name if summary.fault_context else '未知'}

诊断数据：
{self._outputs_to_text(outputs)}

要求：
1. 专业术语准确
2. 逻辑清晰
3. 针对输电线路故障诊断场景
"""

    def _outputs_to_text(self, outputs: Dict[str, ToolOutput]) -> str:
        """将工具输出转为文本"""
        lines = []
        for name, output in outputs.items():
            lines.append(f"【{name}】")
            if output.structured_data:
                for key, value in output.structured_data.items():
                    lines.append(f"  {key}: {value}")
            if output.raw_text:
                lines.append(f"  {output.raw_text}")
        return "\n".join(lines)

    def _assemble_report(self, chapters: List[dict]) -> str:
        """组装完整报告"""
        lines = ["# 输电线路故障诊断报告\n"]
        for chapter in chapters:
            lines.append(f"\n---\n")
            lines.append(chapter["content"])
        return "\n".join(lines)
