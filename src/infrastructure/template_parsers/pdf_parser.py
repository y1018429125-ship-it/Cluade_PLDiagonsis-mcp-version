"""PDF 模板解析器"""

from pathlib import Path
from datetime import datetime

from .base import TemplateParser, ParsedTemplate


class PdfTemplateParser(TemplateParser):
    """解析 .pdf 模板文件"""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> ParsedTemplate:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required for .pdf parsing")

        chapters = []
        lines = [
            f"# {file_path.stem}",
            "",
            f"> 来源文件：{file_path.name}",
            f"> 解析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}",
            f"> 原始格式：pdf",
            "",
            "## 章节结构",
            "",
        ]

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                # 简单启发式：以数字或中文数字开头的短行可能是标题
                for raw_line in text.splitlines():
                    line = raw_line.strip()
                    if 4 <= len(line) <= 30 and (
                        line.startswith(("第", "一", "二", "三", "四", "五")) or
                        (line[0].isdigit() and " " in line)
                    ):
                        chapters.append({"level": 2, "title": line})
                        lines.append(f"### {line}")
                        lines.append(f"- **原始位置**：第{i}页")
                        lines.append("")

        return ParsedTemplate(
            name=file_path.stem,
            source_file=str(file_path),
            source_format="pdf",
            content="\n".join(lines),
            chapters=chapters,
        )
