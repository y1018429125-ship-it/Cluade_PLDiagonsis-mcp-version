"""Tests for src/domain/skill_loader.py — load, list, save, delete skills."""

import pytest

from src.domain.skill_loader import DEFAULT_SKILL_CONTENT, SkillLoader


class TestSkillLoaderFrontmatter:
    def test_load_skill_with_yaml_frontmatter(self, tmp_path):
        """SkillLoader 能解析 YAML frontmatter 和 description"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "test_skill.md"
        skill_file.write_text("""---
name: test_skill
description: |
  当用户提到输电线路故障时触发此技能。
  适用于各种电压等级线路。
---

# 测试技能

## 工具权重

```yaml
weights:
  ToolA: 1.0
  ToolB: 0.8
```
""")
        loader = SkillLoader(str(skills_dir))
        content, weights = loader.load("test_skill")

        assert "name: test_skill" in content
        assert "当用户提到输电线路故障时触发此技能" in content
        assert weights == {"ToolA": 1.0, "ToolB": 0.8}

    def test_load_skill_without_frontmatter(self, tmp_path):
        """无 frontmatter 的 Skill 也能正常加载，weights 从代码块提取"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "legacy.md"
        skill_file.write_text("""# 旧格式技能

```yaml
weights:
  ToolA: 1.0
```
""")
        loader = SkillLoader(str(skills_dir))
        content, weights = loader.load("legacy")

        assert weights == {"ToolA": 1.0}


# ============================================================================
# load
# ============================================================================


def test_load_default_skill(tmp_path) -> None:
    """load() returns file content for an existing skill."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_file = skills_dir / "test_skill.md"
    expected_content = "# Test Skill\n\nThis is a test skill."
    skill_file.write_text(expected_content, encoding="utf-8")

    loader = SkillLoader(skills_dir=str(skills_dir))
    content, weights = loader.load("test_skill")

    assert content == expected_content
    assert weights == {}


def test_load_missing_skill_fallback(tmp_path) -> None:
    """load() returns DEFAULT_SKILL_CONTENT when the skill file is missing."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    loader = SkillLoader(skills_dir=str(skills_dir))
    content, weights = loader.load("nonexistent_skill")

    assert content == DEFAULT_SKILL_CONTENT
    assert weights == {}


# ============================================================================
# list_skills
# ============================================================================


def test_list_skills(tmp_path) -> None:
    """list_skills() returns sorted skill names without .md extension."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "beta_skill.md").write_text("# Beta", encoding="utf-8")
    (skills_dir / "alpha_skill.md").write_text("# Alpha", encoding="utf-8")
    (skills_dir / "gamma_skill.md").write_text("# Gamma", encoding="utf-8")

    loader = SkillLoader(skills_dir=str(skills_dir))
    result = loader.list_skills()

    assert result == ["alpha_skill", "beta_skill", "gamma_skill"]


class TestSkillLoaderMetadata:
    def test_extract_frontmatter_metadata(self, tmp_path):
        """能提取 YAML frontmatter 中的 name 和 description"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "meta_test.md"
        skill_file.write_text("""---
name: meta_test
description: |
  这是描述内容。
  多行描述也应该被保留。
---

# 正文

一些内容。
""")
        loader = SkillLoader(str(skills_dir))
        content, weights = loader.load("meta_test")
        metadata = loader.extract_metadata("meta_test")

        assert metadata["name"] == "meta_test"
        assert "这是描述内容" in metadata["description"]
        assert "多行描述也应该被保留" in metadata["description"]

    def test_load_references(self, tmp_path):
        """能加载 references 目录下的引用文件"""
        skills_dir = tmp_path / "skills"
        refs_dir = skills_dir / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "rules.md").write_text("# 规则\n\n测试规则。\n")

        loader = SkillLoader(str(skills_dir))
        refs = loader.load_references()

        assert "rules.md" in refs
        assert "测试规则" in refs["rules.md"]
