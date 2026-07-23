import pytest
from src.domain.skill_loader import SkillLoader


class TestSkillLoaderWeights:
    def test_extract_weights_from_yaml_block(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "comprehensive_diagnosis.md"
        skill_file.write_text("""# 输电线路综合诊断策略

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 诊断优先级
雷电 > 覆冰 > 风偏 > 鸟害
""")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("comprehensive_diagnosis")

        assert "输电线路综合诊断策略" in content
        assert weights == {
            "LightningDiagnosisTool": 1.0,
            "IcingDiagnosisTool": 0.9,
            "WindDiagnosisTool": 0.8,
            "BirdDamageDiagnosisTool": 0.6,
        }

    def test_extract_weights_no_yaml_block(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "simple.md"
        skill_file.write_text("# Simple Skill\n\nNo weights here.")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("simple")

        assert weights == {}

    def test_extract_weights_invalid_yaml(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "broken.md"
        skill_file.write_text("""# Broken

```yaml
weights:
  Lightning: [invalid
```
""")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("broken")

        assert weights == {}

    def test_extract_weights_cache_hit(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "test.md"
        skill_file.write_text("""# Test

```yaml
weights:
  A: 1.0
```
""")

        loader = SkillLoader(str(skill_dir))
        content1, weights1 = loader.load("test")
        content2, weights2 = loader.load("test")

        assert weights1 == {"A": 1.0}
        assert weights2 == {"A": 1.0}
        assert content1 == content2
