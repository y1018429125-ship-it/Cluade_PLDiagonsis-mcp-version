"""Word 模板解析器"""

from pathlib import Path
from datetime import datetime

from .base import TemplateParser, ParsedTemplate


class DocxTemplateParser(TemplateParser):
    """解析 .docx 模板文件"""

    HEADING_STYLES = {
        "Heading 1", "Heading 2", "Heading 3",
        "标题 1", "标题 2", "标题 3",
    }

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def parse(self, file_path: Path) -> ParsedTemplate:
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required for .docx parsing")

        doc = Document(file_path)
        chapters = []
        lines = [
            f"# {file_path.stem}",
            "",
            f"> 来源文件：{file_path.name}",
            f"> 解析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}",
            f"> 原始格式：docx",
            "",
            "## 章节结构",
            "",
        ]

        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue

            if style in self.HEADING_STYLES:
                if style in ("Heading 1", "标题 1"):
                    level = 1
                elif style in ("Heading 3", "标题 3"):
                    level = 3
                else:
                    level = 2
                chapters.append({"level": level, "title": text})
                lines.append(f"### {text}")
                lines.append(f"- **原始位置**：{style}")
                lines.append("")

        return ParsedTemplate(
            name=file_path.stem,
            source_file=str(file_path),
            source_format="docx",
            content="\n".join(lines),
            chapters=chapters,
        )
