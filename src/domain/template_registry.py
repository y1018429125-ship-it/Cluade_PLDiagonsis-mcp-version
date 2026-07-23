"""模板注册表

管理模板列表、激活状态、解析缓存。
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.infrastructure.template_parsers import (
    DocxTemplateParser,
    MarkdownTemplateParser,
    PdfTemplateParser,
)
from src.infrastructure.template_parsers.base import ParsedTemplate

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("templates/uploads")
PARSED_DIR = Path("templates/parsed")

PARSERS = [
    MarkdownTemplateParser(),
    DocxTemplateParser(),
    PdfTemplateParser(),
]


class TemplateRegistry:
    """模板注册表"""

    def __init__(self):
        self._active_template: Optional[str] = None
        self._ensure_dirs()
        self._load_active()
        self._auto_activate_fallback()

    def _load_active(self) -> None:
        """从持久化文件加载激活状态。"""
        active_file = UPLOADS_DIR / ".active"
        if active_file.exists():
            self._active_template = active_file.read_text(encoding="utf-8").strip() or None

    def _save_active(self) -> None:
        """将激活状态持久化到文件。"""
        active_file = UPLOADS_DIR / ".active"
        if self._active_template:
            active_file.write_text(self._active_template, encoding="utf-8")
        else:
            active_file.unlink(missing_ok=True)

    def _auto_activate_fallback(self) -> None:
        """如果没有激活的模板，自动激活第一个已解析的模板。

        规则：
        - .active 文件存在且指向有效模板 → 保持现状
        - .active 文件存在但指向无效模板 → 清空激活状态，不回退（用户曾手动选择过）
        - .active 文件从未存在且无激活模板 → 自动激活第一个已解析模板
        """
        active_file = UPLOADS_DIR / ".active"
        had_active_file = active_file.exists()

        if self._active_template:
            if not (PARSED_DIR / f"{self._active_template}.md").exists():
                self._active_template = None
                self._save_active()
            return

        if not self._active_template and not had_active_file:
            for p in sorted(PARSED_DIR.iterdir()):
                if p.is_file() and p.suffix == ".md" and not p.name.startswith("."):
                    self._active_template = p.stem
                    self._save_active()
                    logger.info(f"自动激活默认模板: {p.stem}")
                    break

    def _ensure_dirs(self) -> None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        PARSED_DIR.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> List[dict]:
        """列出所有模板（含解析状态）。"""
        if not UPLOADS_DIR.exists():
            return []
        templates = []
        for p in sorted(UPLOADS_DIR.iterdir()):
            if not p.is_file() or p.name.startswith("."):
                continue
            parsed_path = PARSED_DIR / f"{p.stem}.md"
            templates.append({
                "name": p.stem,
                "source_format": p.suffix.lstrip(".").lower(),
                "parsed": parsed_path.exists(),
                "parsed_at": self._get_parsed_at(parsed_path),
                "is_active": p.stem == self._active_template,
            })
        return templates

    def _get_parsed_at(self, parsed_path: Path) -> Optional[str]:
        if parsed_path.exists():
            mtime = datetime.fromtimestamp(parsed_path.stat().st_mtime)
            return mtime.isoformat(timespec="milliseconds")
        return None

    def upload(self, file_path: Path, original_name: str) -> dict:
        """上传模板文件并触发解析。"""
        dest = UPLOADS_DIR / original_name
        shutil.copy(file_path, dest)
        logger.info(f"模板已上传: {dest}")

        # 自动解析
        parsed = self._parse_template(dest)
        if parsed:
            parsed_file = PARSED_DIR / f"{parsed.name}.md"
            parsed_file.write_text(parsed.content, encoding="utf-8")
            logger.info(f"模板已解析: {parsed_file}")

        return {
            "name": dest.stem,
            "source_format": dest.suffix.lstrip(".").lower(),
            "parsed": parsed is not None,
        }

    def _parse_template(self, file_path: Path) -> Optional[ParsedTemplate]:
        """选择合适的解析器解析模板。"""
        for parser in PARSERS:
            if parser.supports(file_path):
                return parser.parse(file_path)
        logger.warning(f"没有可用的解析器: {file_path}")
        return None

    def activate(self, name: str) -> bool:
        """激活指定模板。"""
        parsed_path = PARSED_DIR / f"{name}.md"
        if not parsed_path.exists():
            # 尝试重新解析
            source = UPLOADS_DIR / f"{name}.docx"
            if not source.exists():
                source = UPLOADS_DIR / f"{name}.pdf"
            if not source.exists():
                source = UPLOADS_DIR / f"{name}.md"
            if source.exists():
                parsed = self._parse_template(source)
                if parsed:
                    parsed_file = PARSED_DIR / f"{parsed.name}.md"
                    parsed_file.write_text(parsed.content, encoding="utf-8")
                else:
                    return False
            else:
                return False

        self._active_template = name
        self._save_active()
        logger.info(f"模板已激活: {name}")
        return True

    def get_active(self) -> Optional[str]:
        """获取当前激活的模板名称。"""
        return self._active_template

    def delete(self, name: str) -> bool:
        """删除模板（同时删除 uploads 和 parsed）。"""
        deleted = False
        for ext in [".md", ".docx", ".pdf"]:
            upload_file = UPLOADS_DIR / f"{name}{ext}"
            if upload_file.exists():
                upload_file.unlink()
                deleted = True

        parsed_file = PARSED_DIR / f"{name}.md"
        if parsed_file.exists():
            parsed_file.unlink()
            deleted = True

        if self._active_template == name:
            self._active_template = None
            self._save_active()

        return deleted

    def get_parsed_content(self, name: str) -> Optional[str]:
        """获取解析后的 Markdown 内容。"""
        parsed_path = PARSED_DIR / f"{name}.md"
        if parsed_path.exists():
            return parsed_path.read_text(encoding="utf-8")
        return None
