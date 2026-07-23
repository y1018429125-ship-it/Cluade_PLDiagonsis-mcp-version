import pytest
from pathlib import Path

from src.domain.template_registry import TemplateRegistry


class TestTemplateRegistry:
    @pytest.fixture
    def registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.domain.template_registry.UPLOADS_DIR", tmp_path / "uploads")
        monkeypatch.setattr("src.domain.template_registry.PARSED_DIR", tmp_path / "parsed")
        return TemplateRegistry()

    def test_list_empty(self, registry):
        assert registry.list_templates() == []

    def test_upload_and_parse_markdown(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试模板\n\n## 概述\n")
        result = registry.upload(md_file, "测试模板.md")
        assert result["name"] == "测试模板"
        assert result["parsed"] is True

    def test_activate(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试\n")
        registry.upload(md_file, "测试.md")
        assert registry.activate("测试") is True
        assert registry.get_active() == "测试"

    def test_delete(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试\n")
        registry.upload(md_file, "测试.md")
        assert registry.delete("测试") is True
        assert registry.list_templates() == []

    def test_list_templates_after_upload(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试模板\n")
        registry.upload(md_file, "测试模板.md")
        templates = registry.list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "测试模板"
        assert templates[0]["source_format"] == "md"
        assert templates[0]["parsed"] is True
        assert templates[0]["is_active"] is False

    def test_get_parsed_content(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试内容\n")
        registry.upload(md_file, "测试.md")
        content = registry.get_parsed_content("测试")
        assert content == "# 测试内容\n"

    def test_delete_clears_active(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 测试\n")
        registry.upload(md_file, "测试.md")
        registry.activate("测试")
        assert registry.get_active() == "测试"
        registry.delete("测试")
        assert registry.get_active() is None

    def test_activate_missing_returns_false(self, registry):
        assert registry.activate("不存在的模板") is False

    def test_activate_reparse(self, registry, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# 重新解析测试\n")
        registry.upload(md_file, "重新解析.md")
        assert registry.activate("重新解析") is True

        # 删除解析缓存
        parsed_file = tmp_path / "parsed" / "重新解析.md"
        parsed_file.unlink()
        assert not parsed_file.exists()

        # 重新激活应触发重新解析
        assert registry.activate("重新解析") is True
        assert parsed_file.exists()
