""".docx 模板解析器

解析 Word 文档模板，提取章节结构。
"""

import logging
from pathlib import Path
from typing import List, Optional

from docx import Document

from src.core.models import ChapterConfig, RenderMode, TemplateConfig
from src.core.exceptions import TemplateParseError

logger = logging.getLogger(__name__)


class TemplateParser:
    """模板解析器"""

    # Word 标题样式映射
    HEADING_STYLES = {
        "Heading 1",
        "Heading 2",
        "Heading 3",
        "标题 1",
        "标题 2",
        "标题 3",
    }

    # 章节类型关键词映射
    CHAPTER_KEYWORDS = {
        "overview": ["概述", "简介", "背景"],
        "fault_analysis": ["故障分析", "故障原因", "原因分析"],
        "evidence": ["诊断证据", "证据", "数据", "监测数据"],
        "conclusion": ["诊断结论", "结论", "判定"],
        "recommendation": ["处理建议", "建议", "措施", "处置"],
        "history": ["历史对比", "历史", "对比"],
        "weather": ["气象", "天气", "气象数据"],
    }

    def parse(self, file_path: str | Path) -> TemplateConfig:
        """解析 .docx 模板文件"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise TemplateParseError(f"模板文件不存在: {file_path}")

        try:
            doc = Document(file_path)
            chapters = self._extract_chapters(doc)

            return TemplateConfig(
                name=file_path.stem,
                source_file=str(file_path),
                chapters=chapters,
            )
        except Exception as e:
            logger.error(f"模板解析失败: {e}")
            raise TemplateParseError(f"模板解析失败: {str(e)}")

    def _extract_chapters(self, doc: Document) -> List[ChapterConfig]:
        """从文档中提取章节"""
        chapters = []

        for paragraph in doc.paragraphs:
            if paragraph.style.name in self.HEADING_STYLES:
                title = paragraph.text.strip()
                if title:
                    chapter_type = self._detect_chapter_type(title)
                    chapters.append(
                        ChapterConfig(
                            chapter_type=chapter_type,
                            title=title,
                            required=True,
                        )
                    )

        # 如果没有找到标题，使用默认章节
        if not chapters:
            chapters = self._default_chapters()

        return chapters

    def _detect_chapter_type(self, title: str) -> str:
        """根据标题检测章节类型"""
        title_lower = title.lower()

        for chapter_type, keywords in self.CHAPTER_KEYWORDS.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return chapter_type

        # 未知类型，使用自定义
        return f"custom_{title_lower.replace(' ', '_')}"

    def _default_chapters(self) -> List[ChapterConfig]:
        """默认章节配置"""
        return [
            ChapterConfig(chapter_type="overview", title="概述", required=True),
            ChapterConfig(chapter_type="fault_analysis", title="故障分析", required=True),
            ChapterConfig(chapter_type="evidence", title="诊断证据", required=True),
            ChapterConfig(chapter_type="conclusion", title="诊断结论", required=True),
            ChapterConfig(chapter_type="recommendation", title="处理建议", required=True),
        ]
