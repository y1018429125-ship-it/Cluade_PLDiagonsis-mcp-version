"""模板解析器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedTemplate:
    """解析后的模板结果"""
    name: str
    source_file: str
    source_format: str  # md, docx, pdf
    content: str  # 统一 Markdown 格式
    chapters: list[dict]  # 章节列表


class TemplateParser(ABC):
    """模板解析器抽象基类"""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedTemplate:
        """解析模板文件，返回统一 Markdown 格式。"""
        ...

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """检查是否支持该文件格式。"""
        ...
