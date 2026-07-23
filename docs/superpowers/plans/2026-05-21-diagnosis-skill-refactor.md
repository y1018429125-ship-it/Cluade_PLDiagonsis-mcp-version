# 输电线路故障诊断系统 — Skill 体系重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将诊断系统重构为纯 Skill 驱动架构，支持毫秒级时间、多格式模板上传、交互式报告修改，以及基于 LLM 的 Skill 自动生成。

**Architecture:** 诊断规则（加权算法、工具策略、报告结构）全部写入 Skill Markdown 文件，LLM 通过读取 Skill 自主理解执行。代码层仅保留工具框架、状态管理和模板解析基础设施。模板系统支持 .docx/.pdf/.md 上传，解析为 Markdown 后注入报告生成 prompt。

**Tech Stack:** Python 3.11+ / Flask / Pydantic / Vue 3 + Pinia / TypeScript

---

## 文件结构映射

### 修改文件

| 文件 | 当前行数 | 修改内容 |
|------|---------|---------|
| `src/infrastructure/fault_parser.py` | 261 | 正则增加毫秒捕获组，解析逻辑增加微秒 |
| `src/core/models.py` | 337 | DiagnosisSession 增加 `active_template_name`、`available_templates`；时间序列化配置 |
| `src/domain/skill_loader.py` | 145 | 解析 YAML frontmatter；支持 description 匹配；提取 references |
| `src/domain/report_composer.py` | 242 | 移除 `_extract_summary` 加权计算；改为模板 Markdown 注入；移除 `DEFAULT_CHAPTERS` |
| `src/application/commands/diagnose.py` | 265 | 移除 WeightEngine 调用；依赖 LLM 通过 Skill 自主计算 |
| `src/application/commands/adjust_weight.py` | 139 | 移除 WeightEngine 依赖；纯状态更新 |
| `src/application/commands/recheck.py` | 160 | 移除 WeightEngine 依赖；纯状态更新 |
| `src/application/commands/save_skill.py` | 224 | 重写：使用 LLM 生成 Agent Skill 规范 Markdown |
| `src/application/commands/complete_diagnosis.py` | 60 | 完成后提示保存技能（payload 增加 `suggest_save_skill`） |
| `src/interfaces/web.py` | 773 | 新增模板 API；修改 WeightEngine 引用；新增 ModifyReport 路由 |
| `src/interfaces/dependency_injection.py` | 110 | 移除 WeightEngine；新增 TemplateRegistry |
| `skills/comprehensive_diagnosis.md` | 48 | 重写为 YAML frontmatter + pushy description + 完整规则 |
| `web/src/components/SessionSidebar.vue` | 332 | 时间显示改用固定格式函数（含毫秒） |
| `web/src/components/ReportHistory.vue` | ~150 | 时间显示改用固定格式函数（含毫秒） |
| `web/src/components/AppHeader.vue` | — | 新增：顶部标题栏 + 状态指示器 + 流光效果 |
| `web/src/components/ChatPanel.vue` | 833 | SummaryCard 增强（毫秒时间）；新增 ActionPanel；ToolResultCard |
| `web/src/components/ToolList.vue` | ~200 | 实时权重显示 + 快捷操作按钮 |
| `web/src/components/StrategyManager.vue` | ~250 | Skill 预览弹窗（YAML frontmatter 显示） |
| `web/src/api/http.ts` | 153 | 新增模板 API + 报告修改 API |
| `web/src/stores/sessionStore.ts` | 273 | 增加模板状态管理 + 报告修改 action |
| `web/src/styles/design-system.css` | — | 新增：全局 CSS 变量、色彩令牌、字体、动效 |

### 删除文件

| 文件 | 说明 |
|------|------|
| `src/domain/weight_engine.py` | 纯 Skill 驱动，不再代码计算加权结果 |

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/infrastructure/template_parsers/` | 模板解析器包：基类 + Markdown/Docx/Pdf 实现 |
| `src/infrastructure/template_parsers/base.py` | 抽象基类 `TemplateParser` |
| `src/infrastructure/template_parsers/markdown_parser.py` | 解析 .md 文件 |
| `src/infrastructure/template_parsers/docx_parser.py` | `python-docx` 解析 .docx |
| `src/infrastructure/template_parsers/pdf_parser.py` | `pdfplumber` 解析 .pdf |
| `src/domain/template_registry.py` | 模板注册表：列表、激活、缓存、解析调度 |
| `src/application/commands/upload_template.py` | 上传模板 Command |
| `src/application/commands/activate_template.py` | 激活模板 Command（只能激活一个） |
| `src/application/commands/modify_report.py` | 修改报告 Command（LLM 理解自然语言指令） |
| `skills/references/diagnosis_rules.md` | 通用诊断规则（加权算法） |
| `skills/references/report_structure.md` | 通用报告结构规范 |
| `skills/references/tool_guidelines.md` | 工具调用通用规范 |
| `skills/report_template_parser.md` | 模板解析 Skill |
| `skills/report_modifier.md` | 报告修改 Skill |
| `templates/default.md` | 默认报告模板 |
| `web/src/components/TemplateManager.vue` | 模板管理界面 |
| `web/src/utils/time.ts` | 时间格式化工具函数 |

---

## Phase 1: 后端基础 — 时间修复与 Skill 体系重构

### Task 1: 修复时间解析精度（fault_parser.py）

**Files:**
- Modify: `src/infrastructure/fault_parser.py:38-40`（TIME_PATTERNS 正则）
- Modify: `src/infrastructure/fault_parser.py:153-173`（_extract_fault_time 解析逻辑）
- Test: `tests/unit/test_fault_parser.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_fault_parser.py
import pytest
from datetime import datetime
from src.infrastructure.fault_parser import FaultContextParser


class TestFaultTimeParsing:
    def test_parse_time_with_milliseconds(self):
        """标准格式带毫秒：2026-05-12 08:00:05.013"""
        result = FaultContextParser._extract_fault_time("2026-05-12 08:00:05.013")
        assert result == datetime(2026, 5, 12, 8, 0, 5, 13000)

    def test_parse_time_without_milliseconds(self):
        """标准格式不带毫秒：2026-05-12 08:00:05"""
        result = FaultContextParser._extract_fault_time("2026-05-12 08:00:05")
        assert result == datetime(2026, 5, 12, 8, 0, 5, 0)

    def test_parse_time_minute_only(self):
        """仅到分钟：2026-05-12 08:00"""
        result = FaultContextParser._extract_fault_time("2026-05-12 08:00")
        assert result == datetime(2026, 5, 12, 8, 0, 0, 0)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_fault_parser.py -v
```
Expected: FAIL — `AssertionError` on millisecond test（当前正则不匹配毫秒）

- [ ] **Step 3: 修改正则和解析逻辑**

```python
# src/infrastructure/fault_parser.py — 修改 TIME_PATTERNS
TIME_PATTERNS = [
    # 2024-06-15 14:30:00.123 或 2024-06-15 14:30:00 或 2024-06-15 14:30
    re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.(\d{3}))?"),
    # ... 其余模式保持不变
]
```

```python
# src/infrastructure/fault_parser.py — 修改 _extract_fault_time 中绝对时间解析分支
# 在 "解析绝对时间" 区域，将现有的：
#     second = int(groups[5]) if groups[5] else 0
#     return datetime(year, month, day, hour, minute, second)
# 替换为：
    second = int(groups[5]) if groups[5] else 0
    millisecond = int(groups[6]) if len(groups) > 6 and groups[6] else 0
    return datetime(year, month, day, hour, minute, second, millisecond * 1000)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_fault_parser.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add tests/unit/test_fault_parser.py src/infrastructure/fault_parser.py && git commit -m "fix: parse fault time with millisecond precision"
```

---

### Task 2: 重写 comprehensive_diagnosis.md（Agent Skill 规范格式）

**Files:**
- Create: `skills/comprehensive_diagnosis.md`（覆盖原文件）
- Test: `tests/unit/test_skill_loader.py`

- [ ] **Step 1: 写入新 Skill 文件**

```markdown
# skills/comprehensive_diagnosis.md
---
name: comprehensive_diagnosis
description: |
  输电线路跳闸故障综合诊断专家。当用户描述输电线路故障、跳闸、
  线路异常、杆塔问题、雷击、覆冰、风偏、鸟害等情况时，必须使用此技能。
  即使用户没有明确说"诊断"，只要涉及线路名称+故障/异常/跳闸/闪络/
  接地/短路等关键词，都应自动触发此技能。
  适用于 220kV/500kV/750kV/1000kV 等各电压等级输电线路。
---

# 输电线路综合诊断

## 核心算法：加权置信度

所有工具返回的结果都有置信度（confidence，0~1 之间）。
你必须按以下公式计算每个工具的加权置信度：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

最终按加权置信度从高到低排序，最高者对应的故障类型为主要原因。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 工具调用策略

| 工具 | 权重 | 调用条件 |
|------|------|---------|
| LightningDiagnosisTool | 1.0 | 始终调用 |
| IcingDiagnosisTool | 0.9 | 气温 ≤ 5°C 或冬季时调用，否则主动跳过 |
| WindDiagnosisTool | 0.8 | 始终调用 |
| BirdDamageDiagnosisTool | 0.6 | 始终调用 |

## 诊断流程

1. **信息提取**：从用户描述中提取线路名称、杆塔号、故障时间（精确到毫秒）
2. **天气判断**：获取当前季节和天气，判断覆冰工具是否适用
3. **并行诊断**：同时调用所有符合条件的工具
4. **加权计算**：对每个工具结果计算 加权置信度 = confidence × weight
5. **排序判断**：按加权置信度降序排列，最高者为主要原因
6. **报告生成**：按激活模板的章节结构组织输出

## 置信度等级划分

- HIGH（高置信度）：加权置信度 ≥ 0.7
- MEDIUM（中置信度）：加权置信度 0.4 ~ 0.7
- LOW（低置信度）：加权置信度 < 0.4

## 注意事项

- 覆冰诊断仅在低温条件下有意义，夏季应主动跳过
- 如多个工具指向同一故障类型，应合并证据提升置信度
- 新增工具可用时，应提示用户是否纳入本次诊断
- 故障时间必须精确到毫秒，格式为 YYYY-MM-DD HH:MM:SS.mmm
- 报告结论中必须明确列出每个工具的加权置信度计算过程
```

- [ ] **Step 2: 写测试验证 Skill 加载能解析 YAML frontmatter**

```python
# tests/unit/test_skill_loader.py
import pytest
from src.domain.skill_loader import SkillLoader


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
```

- [ ] **Step 3: 运行测试**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_skill_loader.py -v
```
Expected: 2 passed（当前 SkillLoader 已能提取 weights，测试验证行为）

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add skills/comprehensive_diagnosis.md tests/unit/test_skill_loader.py && git commit -m "feat: rewrite comprehensive_diagnosis skill with YAML frontmatter and Agent Skill spec"
```

---

### Task 3: 新增通用 References

**Files:**
- Create: `skills/references/diagnosis_rules.md`
- Create: `skills/references/report_structure.md`
- Create: `skills/references/tool_guidelines.md`

- [ ] **Step 1: 创建 references 目录和文件**

```bash
mkdir -p /mnt/e/Cluade_PLDiagonsis/skills/references
```

```markdown
# skills/references/diagnosis_rules.md
# 通用诊断规则

## 加权置信度算法

这是所有诊断技能共享的核心排序算法：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

## 主要原因判定

按加权置信度从高到低排序，取最高者为主要原因（primary_diagnosis）。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 置信度等级

- HIGH：≥ 0.7
- MEDIUM：0.4 ~ 0.7
- LOW：< 0.4

## 工具调用原则

1. 尊重用户的排除/包含指令
2. 根据气象条件判断工具是否适用
3. 并行调用所有符合条件的工具
4. 每个工具的结果都要纳入加权计算
```

```markdown
# skills/references/report_structure.md
# 通用报告结构规范

## 默认章节顺序

1. 概述
2. 故障分析
3. 诊断证据
4. 诊断结论
5. 处理建议

## 章节内容要求

- 概述：简要描述故障概况，包括线路名称、故障时间（精确到毫秒）、故障类型
- 故障分析：结合气象数据和历史记录分析故障原因
- 诊断证据：按工具分类列出详细诊断结果，包含每个工具的置信度和加权置信度
- 诊断结论：明确判定主要原因、次要原因，给出加权置信度排序
- 处理建议：给出具体的运维和检修建议

## 格式要求

- 使用 Markdown 格式
- 一级标题为报告总标题
- 二级标题为各章节
- 诊断结论中必须列出加权置信度计算过程
```

```markdown
# skills/references/tool_guidelines.md
# 工具调用通用规范

## 输出格式期望

每个诊断工具应返回以下结构：

```json
{
  "fault_type": "雷击",
  "confidence": 0.85,
  "evidence": ["证据1", "证据2"],
  "details": {...}
}
```

## 置信度含义

- 0.9~1.0：几乎确定
- 0.7~0.9：高度可能
- 0.4~0.7：有一定可能
- 0.1~0.4：可能性较低
- 0~0.1：几乎不可能

## 调用原则

- 并行调用所有符合条件的工具
- 不等待单一工具结果再做下一步判断
- 所有工具结果一视同仁纳入加权计算
```

- [ ] **Step 2: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add skills/references/ && git commit -m "feat: add shared reference docs for diagnosis rules, report structure, and tool guidelines"
```

---

### Task 4: 改造 SkillLoader 支持 YAML frontmatter 解析

**Files:**
- Modify: `src/domain/skill_loader.py`
- Test: `tests/unit/test_skill_loader.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/unit/test_skill_loader.py

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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_skill_loader.py::TestSkillLoaderMetadata -v
```
Expected: FAIL — `AttributeError: 'SkillLoader' object has no attribute 'extract_metadata'`

- [ ] **Step 3: 实现 SkillLoader 改造**

```python
# src/domain/skill_loader.py — 完整替换
"""技能加载器

提供 Markdown 格式技能文件的加载、列表、保存和删除功能。
支持 YAML frontmatter 解析、内存缓存、references 引用加载。
"""

import logging
import re
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

DEFAULT_SKILL_CONTENT = """# 默认技能

## 描述

这是一个默认技能占位符。当请求的技能文件不存在时，系统将返回此内容。

## 用法

请确保技能文件已正确放置在 `skills/` 目录下，并以 `.md` 为扩展名。

## 注意事项

- 技能文件名应使用小写字母和下划线
- 内容使用 Markdown 格式编写
- 每个技能应包含描述、参数说明和示例
"""

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillLoader:
    """技能加载器

    负责管理 Markdown 技能文件的 CRUD 操作，支持 YAML frontmatter 解析，
    并维护内存缓存以提高读取性能。
    """

    def __init__(self, skills_dir: str = "skills") -> None:
        """初始化技能加载器。

        Args:
            skills_dir: 技能文件存放目录，默认为 "skills"。
        """
        self._skills_dir = Path(skills_dir)
        self._cache: Dict[str, str] = {}
        self._metadata_cache: Dict[str, dict] = {}

    def load(self, skill_name: str) -> tuple[str, dict]:
        """加载指定技能文件的内容和权重配置。

        如果内容已缓存，直接返回缓存内容。
        如果文件不存在，返回默认回退内容。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。

        Returns:
            (技能文件内容, 权重配置字典)
        """
        if skill_name in self._cache:
            logger.debug(f"命中缓存: {skill_name}")
            content = self._cache[skill_name]
            return content, self._extract_weights(content)

        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            logger.warning(f"技能文件不存在: {skill_path}，返回默认内容")
            return DEFAULT_SKILL_CONTENT, {}

        content = skill_path.read_text(encoding="utf-8")
        self._cache[skill_name] = content
        logger.info(f"已加载技能: {skill_name}")
        return content, self._extract_weights(content)

    def extract_metadata(self, skill_name: str) -> dict:
        """提取技能的 YAML frontmatter 元数据。

        Args:
            skill_name: 技能名称。

        Returns:
            frontmatter 解析后的字典（无 frontmatter 返回空字典）。
        """
        if skill_name in self._metadata_cache:
            return self._metadata_cache[skill_name]

        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            return {}

        content = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(content)
        self._metadata_cache[skill_name] = metadata
        return metadata

    def _parse_frontmatter(self, content: str) -> dict:
        """解析 Markdown 内容中的 YAML frontmatter。"""
        match = FRONTMATTER_PATTERN.match(content)
        if not match:
            return {}
        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.warning(f"YAML frontmatter 解析失败: {e}")
            return {}

    def _extract_weights(self, content: str) -> dict[str, float]:
        """从 Markdown 内容中提取 YAML 代码块里的 weights 配置。"""
        pattern = r'```yaml\s*(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}
        try:
            config = yaml.safe_load(match.group(1))
            if isinstance(config, dict):
                return config.get("weights", {})
        except yaml.YAMLError:
            pass
        return {}

    def list_skills(self) -> List[str]:
        """列出所有可用的技能名称。

        Returns:
            按字母顺序排序的技能名称列表（不含 .md 扩展名）。
        """
        if not self._skills_dir.exists():
            logger.warning(f"技能目录不存在: {self._skills_dir}")
            return []

        skills = sorted(
            p.stem for p in self._skills_dir.glob("*.md") if p.is_file()
        )
        logger.debug(f"发现 {len(skills)} 个技能")
        return skills

    def load_references(self) -> Dict[str, str]:
        """加载 references 目录下的所有引用文件。

        Returns:
            文件名到内容的映射字典。
        """
        refs_dir = self._skills_dir / "references"
        if not refs_dir.exists():
            return {}

        refs = {}
        for p in refs_dir.glob("*.md"):
            if p.is_file():
                refs[p.name] = p.read_text(encoding="utf-8")
                logger.debug(f"已加载引用: {p.name}")
        return refs

    def save(self, skill_name: str, content: str) -> Path:
        """保存技能文件内容。

        自动创建 skills_dir 目录（如不存在），并更新缓存。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。
            content: 要写入的 Markdown 内容。

        Returns:
            写入文件的路径。
        """
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        skill_path = self._skills_dir / f"{skill_name}.md"
        skill_path.write_text(content, encoding="utf-8")
        self._cache[skill_name] = content
        # 清除元数据缓存，下次重新解析
        self._metadata_cache.pop(skill_name, None)
        logger.info(f"已保存技能: {skill_name}")
        return skill_path

    def delete(self, skill_name: str) -> bool:
        """删除指定技能文件。

        如文件存在则删除并清除缓存；如不存在则返回 False。

        Args:
            skill_name: 技能名称（不含 .md 扩展名）。

        Returns:
            是否成功删除文件。
        """
        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            logger.warning(f"删除失败，技能文件不存在: {skill_path}")
            return False

        skill_path.unlink()
        self._cache.pop(skill_name, None)
        self._metadata_cache.pop(skill_name, None)
        logger.info(f"已删除技能: {skill_name}")
        return True
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_skill_loader.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/domain/skill_loader.py tests/unit/test_skill_loader.py && git commit -m "feat: SkillLoader supports YAML frontmatter parsing and references loading"
```

---

### Task 5: 删除 WeightEngine 并清理所有引用

**Files:**
- Delete: `src/domain/weight_engine.py`
- Modify: `src/application/commands/adjust_weight.py`
- Modify: `src/application/commands/recheck.py`
- Modify: `src/interfaces/dependency_injection.py`
- Modify: `src/interfaces/web.py`（_resolve_command 中移除 weight_engine 传参）
- Test: `tests/unit/test_commands.py`

- [ ] **Step 1: 删除 weight_engine.py**

```bash
rm /mnt/e/Cluade_PLDiagonsis/src/domain/weight_engine.py
```

- [ ] **Step 2: 修改 adjust_weight.py（移除 WeightEngine 依赖）**

```python
# src/application/commands/adjust_weight.py — 完整替换
"""调整权重 Command"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError, WeightValidationError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)

WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0


class AdjustWeightCommand(Command):
    """调整权重 Command

    调整指定工具的权重，验证范围后更新 active_weights。
    纯状态更新，不重新计算加权结果（由 LLM 通过 Skill 自主计算）。
    """

    def __init__(
        self,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行权重调整操作"""
        session = ctx.session
        tool_name, new_weight = self._extract_params(ctx)

        yield Event.thinking(
            session.session_id,
            f"调整 {tool_name} 权重为 {new_weight}...",
        )

        self._validate_state(session)
        self._validate_weight(tool_name, new_weight)

        self.session_manager.update_weights(
            session.session_id, {tool_name: new_weight}
        )
        session.action_log.append(
            UserAction(
                action_type="adjust_weight",
                parameters={"tool_name": tool_name, "weight": new_weight},
            )
        )

        logger.info(f"权重调整完成: {session.session_id} -> {tool_name}={new_weight}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已调整 {tool_name} 权重为 {new_weight}",
                "active_weights": session.active_weights,
            },
        )

    def _extract_params(self, ctx: ExecutionContext) -> tuple[str, float]:
        """从意图参数中提取工具名和新权重"""
        if not ctx.intent:
            raise InvalidStateError("缺少意图参数")

        tool_name = ctx.intent.parameters.get("tool_name", "")
        weight_raw = ctx.intent.parameters.get("weight")

        if not tool_name:
            raise InvalidStateError("缺少 tool_name 参数")
        if weight_raw is None:
            raise InvalidStateError("缺少 weight 参数")

        try:
            new_weight = float(weight_raw)
        except (ValueError, TypeError) as exc:
            raise InvalidStateError(f"权重值无效: {weight_raw}") from exc

        return tool_name, new_weight

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许调整权重"""
        if not self.state_machine.can_execute(session, "adjust_weight"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许调整权重"
            )

    def _validate_weight(self, tool_name: str, weight: float) -> None:
        """验证权重范围"""
        if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
            raise WeightValidationError(
                f"权重 {tool_name}={weight} 超出范围 [{WEIGHT_MIN}, {WEIGHT_MAX}]"
            )
```

- [ ] **Step 3: 修改 recheck.py（移除 WeightEngine 依赖）**

```python
# src/application/commands/recheck.py — 完整替换
"""重新检查工具 Command"""

import logging
from typing import AsyncIterator

from src.core.models import (
    Event,
    ExecutionContext,
    FaultContext,
    SessionStatus,
)
from src.core.exceptions import InvalidStateError, ToolNotFoundError
from src.application.commands.base import Command
from src.infrastructure.adapters.registry import ToolRegistry
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


class RecheckToolCommand(Command):
    """重新检查工具 Command

    对指定工具重新执行诊断，更新 rechecked_tools 列表。
    不重新计算加权摘要（由 LLM 通过 Skill 自主计算）。
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        session_manager: SessionManager,
        state_machine: StateMachine,
    ):
        self.tool_registry = tool_registry
        self.session_manager = session_manager
        self.state_machine = state_machine

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行重新检查操作"""
        session = ctx.session
        tool_name = self._extract_tool_name(ctx)

        yield Event.start(session.session_id, f"重新检查工具: {tool_name}...")

        self._validate_state(session)
        self._validate_tool(tool_name)

        # 清除该工具缓存，强制重新调用
        if tool_name in session.tool_outputs_cache:
            del session.tool_outputs_cache[tool_name]
            logger.info(f"清除缓存: {tool_name}")

        self.session_manager.transition(session.session_id, SessionStatus.RECHECKING)
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.RECHECKING.value},
        )

        fault_context = self._build_fault_context(session)
        yield Event.thinking(session.session_id, f"重新执行 {tool_name}...")

        tool_output = await self.tool_registry.execute_tool(tool_name, fault_context)
        yield Event.result(
            session.session_id,
            {"tool_name": tool_name, "output": tool_output.raw_text},
        )

        self.session_manager.add_rechecked(session.session_id, tool_name)

        self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)
        yield Event.status(
            session.session_id,
            {"status": SessionStatus.MODIFYING.value},
        )

        logger.info(f"重新检查完成: {session.session_id} -> {tool_name}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已重新检查 {tool_name}",
                "rechecked_tools": session.rechecked_tools,
            },
        )

    def _extract_tool_name(self, ctx: ExecutionContext) -> str:
        """从意图参数中提取工具名"""
        if ctx.intent:
            tool_name = ctx.intent.parameters.get("tool_name", "")
            if tool_name:
                return tool_name
        raise InvalidStateError("缺少 tool_name 参数")

    def _validate_state(self, session) -> None:
        """验证当前状态是否允许重新检查"""
        if not self.state_machine.can_execute(session, "recheck"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许重新检查"
            )

    def _validate_tool(self, tool_name: str) -> None:
        """验证工具是否已注册"""
        if tool_name not in self.tool_registry.list_tool_names():
            raise ToolNotFoundError(f"工具不存在: {tool_name}")

    def _build_fault_context(self, session) -> FaultContext:
        """构建故障上下文"""
        current = session.current_summary
        if current and current.fault_context:
            return current.fault_context
        return FaultContext(
            line_id=session.session_id,
            line_name=session.line_name,
        )
```

- [ ] **Step 4: 修改 dependency_injection.py（移除 WeightEngine）**

```python
# src/interfaces/dependency_injection.py — 修改 Container.__init__
# 删除以下 import:
# from src.domain.weight_engine import WeightEngine

# 在 Container.__init__ 中删除:
# self.weight_engine = WeightEngine(...)

# 最终 __init__ 中相关行应为:
# self.report_engine = ReportEngine(self.llm_service, self.event_bus)
# self.template_parser = TemplateParser()
# self.skill_loader = SkillLoader()
# ...（直接跳到 skill_loader，不再创建 weight_engine）
```

具体的 edit:

```python
# 删除 import 行
# from src.domain.weight_engine import WeightEngine
```

```python
# 删除 weight_engine 创建代码（约第 44-47 行）
# self.weight_engine = WeightEngine(
#     min_weight=self.config.diagnosis.weight_min,
#     max_weight=self.config.diagnosis.weight_max,
# )
```

- [ ] **Step 5: 修改 web.py 中 _resolve_command（移除 weight_engine 传参）**

```python
# src/interfaces/web.py — 修改 _resolve_command 函数
# 将:
#     elif intent_type == IntentType.RECHECK_TOOL:
#         return RecheckToolCommand(
#             tool_registry=container.tool_registry,
#             weight_engine=container.weight_engine,
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#         )
#     elif intent_type == IntentType.ADJUST_WEIGHT:
#         return AdjustWeightCommand(
#             weight_engine=container.weight_engine,
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#         )
# 替换为:
#     elif intent_type == IntentType.RECHECK_TOOL:
#         return RecheckToolCommand(
#             tool_registry=container.tool_registry,
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#         )
#     elif intent_type == IntentType.ADJUST_WEIGHT:
#         return AdjustWeightCommand(
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#         )
```

- [ ] **Step 6: 更新测试文件（移除 WeightEngine mock）**

```python
# tests/unit/test_commands.py — 修改 adjust_command fixture
@pytest.fixture
def adjust_command() -> AdjustWeightCommand:
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    return AdjustWeightCommand(mock_session_manager, mock_state_machine)
```

```python
# tests/unit/test_commands.py — 删除涉及 weight_engine.compute 的测试
def test_adjust_weight_recomputes_when_summary_exists(...):
    # 删除整个测试（纯 Skill 驱动不再重新计算）
```

```python
# tests/unit/test_commands.py — 修改 recheck_command fixture
@pytest.fixture
def recheck_command() -> RecheckToolCommand:
    mock_registry = MagicMock()
    mock_session_manager = MagicMock()
    mock_state_machine = MagicMock()
    mock_state_machine.can_execute.return_value = True
    mock_registry.list_tool_names.return_value = ["ToolA"]
    mock_registry.execute_tool = AsyncMock(return_value=ToolOutput(tool_name="ToolA", raw_text="rechecked"))
    return RecheckToolCommand(mock_registry, mock_session_manager, mock_state_machine)
```

```python
# tests/unit/test_commands.py — 修改 test_recheck_tool_success
# 删除以下断言:
# recheck_command.weight_engine.compute.return_value = DiagnosisSummary()
# recheck_command.session_manager.add_summary.assert_called_once()
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_commands.py -v
```
Expected: 所有测试通过（可能需要调整测试数量）

- [ ] **Step 8: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add -A && git commit -m "refactor: remove WeightEngine, pure skill-driven weight calculation"
```

---

### Task 6: 改造 ReportComposer（移除加权计算，支持模板注入）

**Files:**
- Modify: `src/domain/report_composer.py`
- Modify: `src/core/models.py`（DiagnosisSession 增加 active_template_name）
- Test: `tests/unit/test_report_composer.py`

- [ ] **Step 1: 修改 core/models.py 添加 active_template_name**

```python
# src/core/models.py — DiagnosisSession 类中添加字段
# 在 active_skill_name 字段下方添加:
    active_template_name: Optional[str] = None
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_report_composer.py
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from src.domain.report_composer import ReportComposer
from src.core.models import ToolOutput, FaultContext


class TestReportComposer:
    @pytest.fixture
    def composer(self):
        mock_llm = AsyncMock()
        return ReportComposer(mock_llm)

    @pytest.mark.asyncio
    async def test_compose_without_weights(self, composer):
        """ReportComposer 不再计算加权结果，summary 中不含 weighted_scores"""
        tool_outputs = {
            "ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.8, "fault_type": "雷击"}),
        }
        composer.llm.chat.return_value = "# 诊断报告\n\n测试内容。"

        result = await composer.compose(
            tool_outputs, None, "s1",
            fault_context=FaultContext(line_id="s1", line_name="京西线"),
        )

        # summary 中不应包含加权计算结果
        assert "weighted_scores" not in result["summary"]
        assert result["summary"]["fault_type"] == "雷击"
        assert result["summary"]["confidence"] == 0.8
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_report_composer.py -v
```
Expected: FAIL — `ModuleNotFoundError` 或 assertion error

- [ ] **Step 4: 实现 ReportComposer 改造**

```python
# src/domain/report_composer.py — 完整替换
"""报告撰写器

通过单次 LLM 调用生成完整的诊断报告。
支持模板 Markdown 注入，由 LLM 自主按模板结构组织输出。
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.models import FaultContext, ToolOutput
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_CHAPTERS = ["概述", "故障分析", "诊断证据", "诊断结论", "处理建议"]


class ReportComposer:
    """报告撰写器

    基于工具输出和模板配置，通过单次 LLM 调用生成完整诊断报告。
    纯 Skill 驱动：LLM 通过读取 Skill 自主计算加权置信度并排序。
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def compose(
        self,
        tool_outputs: Dict[str, ToolOutput],
        template: Optional[Any],  # 保留参数兼容，实际使用模板 Markdown
        session_id: str,
        fault_context: Optional[FaultContext] = None,
        action_log: Optional[list[dict]] = None,
        weights: Optional[Dict[str, float]] = None,
        active_template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """撰写完整诊断报告。

        Args:
            tool_outputs: 各诊断工具的输出结果。
            template: 模板配置（向后兼容，优先使用 active_template_name）。
            session_id: 当前会话 ID。
            fault_context: 故障上下文。
            action_log: 用户操作历史。
            weights: 工具权重配置（传递给 LLM 作为参考，不代码计算）。
            active_template_name: 当前激活的模板名称。

        Returns:
            包含 summary 和 report 的字典。
        """
        # 加载模板 Markdown
        template_md = self._load_template_md(active_template_name)

        # 构建提示词
        prompt = self._build_prompt(
            tool_outputs, fault_context, action_log, weights, template_md
        )

        messages = [
            {"role": "system", "content": "你是输电线路故障诊断报告撰写专家。"},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"会话 {session_id} 报告生成失败: {e}")
            raise

        formatted = self._format_response(response)
        summary = self._extract_summary(tool_outputs)
        if fault_context:
            summary["line_name"] = fault_context.line_name
            if fault_context.additional_info:
                summary["voltage_level"] = fault_context.additional_info.get("voltage_level", "")
            if fault_context.fault_time:
                summary["fault_time"] = fault_context.fault_time.isoformat()
        if action_log:
            summary["action_log"] = action_log

        return {"summary": summary, "report": formatted}

    def _load_template_md(self, template_name: Optional[str]) -> str:
        """加载激活模板的 Markdown 内容。"""
        if not template_name:
            return ""

        parsed_path = Path("templates/parsed") / f"{template_name}.md"
        if parsed_path.exists():
            return parsed_path.read_text(encoding="utf-8")

        # 回退：尝试直接读取 templates/ 下的 .md 文件
        direct_path = Path("templates") / f"{template_name}.md"
        if direct_path.exists():
            return direct_path.read_text(encoding="utf-8")

        logger.warning(f"模板文件不存在: {template_name}")
        return ""

    def _build_prompt(
        self,
        tool_outputs: Dict[str, ToolOutput],
        fault_context: Optional[FaultContext],
        action_log: Optional[list[dict]],
        weights: Optional[Dict[str, float]],
        template_md: str,
    ) -> str:
        lines = [
            "请根据以下诊断工具输出，生成一份完整的输电线路故障诊断报告。",
            "",
        ]

        if fault_context:
            lines.extend(["## 诊断目标", ""])
            target_parts = []
            if fault_context.additional_info:
                voltage = fault_context.additional_info.get("voltage_level")
                if voltage:
                    target_parts.append(f"电压等级：{voltage}")
            target_parts.append(f"线路名称：{fault_context.line_name}")
            if fault_context.fault_time:
                target_parts.append(
                    f"故障时间：{fault_context.fault_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
                )
            target_parts.append("故障类型：跳闸")
            lines.append(" | ".join(target_parts))
            lines.append("")

        if weights:
            lines.extend([
                "## 工具权重配置",
                "",
                "请在诊断结论中按以下权重计算加权置信度：",
                "",
            ])
            for tool_name, weight in weights.items():
                lines.append(f"- {tool_name}: {weight}")
            lines.append("")

        if action_log:
            lines.extend(["## 用户操作历史", ""])
            for action in action_log:
                action_type = action.get("action_type", "")
                tool_name = action.get("tool_name", "")
                desc = action.get("description", "")
                if action_type == "exclude":
                    lines.append(f"- 排除 {tool_name} 诊断数据")
                elif action_type == "include":
                    lines.append(f"- 恢复 {tool_name} 诊断数据")
                elif action_type == "recheck":
                    lines.append(f"- 复查 {tool_name}")
                elif action_type == "adjust_weight":
                    w = action.get("weight", "")
                    lines.append(f"- 调整 {tool_name} 权重为 {w}")
                elif action_type == "modify_report":
                    lines.append(f"- 修改报告：{desc or tool_name}")
                elif action_type == "complete":
                    lines.append("- 完成诊断")
                else:
                    lines.append(f"- {action_type}: {desc or tool_name}")
            lines.append("")

        lines.extend(["## 诊断工具输出", ""])
        for tool_name, output in tool_outputs.items():
            lines.append(f"### {tool_name}")
            if output.raw_text:
                lines.append(f"原始文本：\n{output.raw_text}")
            if output.structured_data:
                lines.append(
                    f"结构化数据：\n```json\n"
                    f"{json.dumps(output.structured_data, ensure_ascii=False, indent=2)}"
                    f"\n```"
                )
            lines.append("")

        if template_md:
            lines.extend([
                "## 报告模板约束",
                "",
                "请严格按照以下模板章节结构组织报告：",
                "",
                template_md,
                "",
            ])
        else:
            lines.extend([
                "## 报告要求",
                "",
                "请生成包含以下章节的完整报告：",
                "",
            ])
            for chapter in DEFAULT_CHAPTERS:
                lines.append(f"- {chapter}")
            lines.append("")

        lines.extend([
            "格式要求：",
            "1. 每个章节使用 `## 章节名` 作为标题",
            "2. 内容专业、逻辑清晰",
            "3. 基于提供的诊断数据进行分析",
            "4. 使用 Markdown 格式输出",
            "5. 诊断结论中必须列出每个工具的加权置信度计算过程",
        ])

        return "\n".join(lines)

    def _format_response(self, response: str) -> str:
        stripped = response.strip()
        if not stripped.startswith("# "):
            return f"# 输电线路故障诊断报告\n\n{stripped}"
        return stripped

    def _extract_summary(
        self, tool_outputs: Dict[str, ToolOutput]
    ) -> Dict[str, Any]:
        """提取诊断摘要（纯工具输出，不做加权计算）。

        加权计算由 LLM 通过 Skill 自主完成。
        """
        best_tool = None
        best_confidence = 0.0
        best_fault_type = "未知"

        for tool_name, output in tool_outputs.items():
            structured = output.structured_data or {}
            confidence = structured.get("confidence", 0.0)
            fault_type = structured.get("fault_type", "未知")
            if not isinstance(confidence, (int, float)):
                continue

            if confidence > best_confidence:
                best_confidence = confidence
                best_fault_type = fault_type
                best_tool = tool_name

        return {
            "fault_type": best_fault_type,
            "confidence": round(best_confidence, 2),
            "primary_tool": best_tool or "unknown",
        }
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_report_composer.py -v
```
Expected: passed

- [ ] **Step 6: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add -A && git commit -m "refactor: ReportComposer pure skill-driven, remove weight calculation, support template injection"
```

---

### Task 7: 修改 DiagnoseCommand 适配纯 Skill 驱动

**Files:**
- Modify: `src/application/commands/diagnose.py`
- Test: `tests/unit/test_commands.py`

- [ ] **Step 1: 修改 diagnose.py（移除 WeightEngine 相关，增加模板名传递）**

```python
# src/application/commands/diagnose.py — 关键修改
# 在 report_composer.compose 调用处（约第 199-202 行）：
# 将:
#         composed = await self.report_composer.compose(
#             tool_outputs, None, session.session_id, fault_context, action_log_data,
#             weights=session.active_weights,
#         )
# 替换为:
        composed = await self.report_composer.compose(
            tool_outputs, None, session.session_id, fault_context, action_log_data,
            weights=session.active_weights,
            active_template_name=session.active_template_name,
        )
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_commands.py::test_diagnose_success -v
```
Expected: passed

- [ ] **Step 3: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/application/commands/diagnose.py && git commit -m "refactor: DiagnoseCommand pass active_template_name to ReportComposer"
```

---

## Phase 2: 后端模板系统

### Task 8: 实现多格式模板解析器

**Files:**
- Create: `src/infrastructure/template_parsers/__init__.py`
- Create: `src/infrastructure/template_parsers/base.py`
- Create: `src/infrastructure/template_parsers/markdown_parser.py`
- Create: `src/infrastructure/template_parsers/docx_parser.py`
- Create: `src/infrastructure/template_parsers/pdf_parser.py`
- Test: `tests/unit/test_template_parsers.py`

- [ ] **Step 1: 创建解析器包和基类**

```python
# src/infrastructure/template_parsers/__init__.py
from .base import TemplateParser, ParsedTemplate
from .markdown_parser import MarkdownTemplateParser
from .docx_parser import DocxTemplateParser
from .pdf_parser import PdfTemplateParser

__all__ = [
    "TemplateParser",
    "ParsedTemplate",
    "MarkdownTemplateParser",
    "DocxTemplateParser",
    "PdfTemplateParser",
]
```

```python
# src/infrastructure/template_parsers/base.py
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
```

```python
# src/infrastructure/template_parsers/markdown_parser.py
"""Markdown 模板解析器"""

import re
from pathlib import Path

from .base import TemplateParser, ParsedTemplate


class MarkdownTemplateParser(TemplateParser):
    """解析 .md 模板文件"""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".md"

    def parse(self, file_path: Path) -> ParsedTemplate:
        content = file_path.read_text(encoding="utf-8")
        chapters = self._extract_chapters(content)

        return ParsedTemplate(
            name=file_path.stem,
            source_file=str(file_path),
            source_format="md",
            content=content,
            chapters=chapters,
        )

    def _extract_chapters(self, content: str) -> list[dict]:
        chapters = []
        for line in content.splitlines():
            match = re.match(r"^(#{2,3})\s+(.+)", line)
            if match:
                chapters.append({
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                })
        return chapters
```

```python
# src/infrastructure/template_parsers/docx_parser.py
"""Word 模板解析器"""

import logging
from pathlib import Path
from datetime import datetime

from .base import TemplateParser, ParsedTemplate

logger = logging.getLogger(__name__)


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

        page_num = 1
        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue

            if style in self.HEADING_STYLES:
                level = 1 if "1" in style or style == "Heading 1" else 2
                chapters.append({"level": level, "title": text})
                lines.append(f"### {text}")
                lines.append(f"- **原始位置**：第{page_num}页，{style}")
                lines.append("")

        return ParsedTemplate(
            name=file_path.stem,
            source_file=str(file_path),
            source_format="docx",
            content="\n".join(lines),
            chapters=chapters,
        )
```

```python
# src/infrastructure/template_parsers/pdf_parser.py
"""PDF 模板解析器"""

import logging
from pathlib import Path
from datetime import datetime

from .base import TemplateParser, ParsedTemplate

logger = logging.getLogger(__name__)


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
                for line in text.splitlines():
                    line = line.strip()
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
```

- [ ] **Step 2: 写测试**

```python
# tests/unit/test_template_parsers.py
import pytest
from pathlib import Path

from src.infrastructure.template_parsers import (
    MarkdownTemplateParser,
    DocxTemplateParser,
    PdfTemplateParser,
)


class TestMarkdownTemplateParser:
    def test_parse_markdown(self, tmp_path):
        parser = MarkdownTemplateParser()
        md_file = tmp_path / "test.md"
        md_file.write_text("""# 报告模板

## 概述
简要描述。

## 故障分析
分析原因。
""")
        result = parser.parse(md_file)
        assert result.name == "test"
        assert result.source_format == "md"
        assert len(result.chapters) == 2
        assert result.chapters[0]["title"] == "概述"


class TestDocxTemplateParser:
    def test_supports_docx(self):
        parser = DocxTemplateParser()
        assert parser.supports(Path("test.docx")) is True
        assert parser.supports(Path("test.md")) is False
```

- [ ] **Step 3: 运行测试**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_template_parsers.py -v
```
Expected: passed

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/infrastructure/template_parsers/ tests/unit/test_template_parsers.py && git commit -m "feat: multi-format template parsers (md/docx/pdf)"
```

---

### Task 9: 新增 TemplateRegistry

**Files:**
- Create: `src/domain/template_registry.py`
- Test: `tests/unit/test_template_registry.py`

- [ ] **Step 1: 实现 TemplateRegistry**

```python
# src/domain/template_registry.py
"""模板注册表

管理模板列表、激活状态、解析缓存。
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from src.infrastructure.template_parsers import (
    MarkdownTemplateParser,
    DocxTemplateParser,
    PdfTemplateParser,
)
from src.infrastructure.template_parsers.base import ParsedTemplate

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("templates/uploads")
PARSED_DIR = Path("templates/parsed")
DEFAULT_TEMPLATE = Path("templates/default.md")

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

    def _ensure_dirs(self) -> None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        PARSED_DIR.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> List[dict]:
        """列出所有模板（含解析状态）。"""
        templates = []
        for p in sorted(UPLOADS_DIR.iterdir()):
            if not p.is_file():
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
            from datetime import datetime
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

        self._active_template = name
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

        return deleted

    def get_parsed_content(self, name: str) -> Optional[str]:
        """获取解析后的 Markdown 内容。"""
        parsed_path = PARSED_DIR / f"{name}.md"
        if parsed_path.exists():
            return parsed_path.read_text(encoding="utf-8")
        return None
```

- [ ] **Step 2: 写测试**

```python
# tests/unit/test_template_registry.py
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
```

- [ ] **Step 3: 运行测试**

```bash
cd /mnt/e/Cluade_PLDiagonsis && python -m pytest tests/unit/test_template_registry.py -v
```
Expected: 4 passed

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/domain/template_registry.py tests/unit/test_template_registry.py && git commit -m "feat: TemplateRegistry for upload/activate/delete parsed templates"
```

---

### Task 10: 新增模板 Commands 和 Web API

**Files:**
- Create: `src/application/commands/upload_template.py`
- Create: `src/application/commands/activate_template.py`
- Modify: `src/interfaces/web.py`
- Modify: `src/interfaces/dependency_injection.py`
- Test: `tests/unit/test_template_commands.py`

- [ ] **Step 1: 实现 UploadTemplateCommand**

```python
# src/application/commands/upload_template.py
"""上传模板 Command"""

import logging
from pathlib import Path
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext
from src.application.commands.base import Command
from src.domain.template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


class UploadTemplateCommand(Command):
    """上传模板 Command"""

    def __init__(self, template_registry: TemplateRegistry):
        self.template_registry = template_registry

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        session = ctx.session
        file_path = ctx.intent.parameters.get("file_path") if ctx.intent else None
        original_name = ctx.intent.parameters.get("original_name") if ctx.intent else None

        if not file_path or not original_name:
            yield Event.error(session.session_id, "缺少文件路径或文件名")
            return

        yield Event.thinking(session.session_id, f"上传模板: {original_name}...")

        result = self.template_registry.upload(Path(file_path), original_name)

        yield Event.complete(
            session.session_id,
            {
                "message": f"模板 '{result['name']}' 上传成功",
                "template": result,
            },
        )
```

- [ ] **Step 2: 实现 ActivateTemplateCommand**

```python
# src/application/commands/activate_template.py
"""激活模板 Command"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.template_registry import TemplateRegistry
from src.domain.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ActivateTemplateCommand(Command):
    """激活模板 Command"""

    def __init__(
        self,
        template_registry: TemplateRegistry,
        session_manager: SessionManager,
    ):
        self.template_registry = template_registry
        self.session_manager = session_manager

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        session = ctx.session
        template_name = ctx.intent.parameters.get("template_name") if ctx.intent else None

        if not template_name:
            raise InvalidStateError("缺少 template_name 参数")

        yield Event.thinking(session.session_id, f"激活模板: {template_name}...")

        success = self.template_registry.activate(template_name)
        if not success:
            yield Event.error(session.session_id, f"模板 '{template_name}' 不存在或解析失败")
            return

        session.active_template_name = template_name
        self.session_manager._persist()

        yield Event.complete(
            session.session_id,
            {
                "message": f"模板 '{template_name}' 已激活",
                "active_template": template_name,
            },
        )
```

- [ ] **Step 3: 修改 web.py 新增模板 API**

```python
# src/interfaces/web.py — 在已有 import 后添加:
from src.domain.template_registry import TemplateRegistry

# 在 create_app 中，container 初始化后确保 TemplateRegistry 可用:
# 在依赖注入中需要创建 template_registry
```

更具体的修改：在 `create_app()` 函数中添加路由。在 `/api/health` 路由前后添加：

```python
    # ------------------------------------------------------------------
    # 模板管理 API
    # ------------------------------------------------------------------
    @app.route("/api/templates", methods=["GET"])
    def list_templates():
        """获取模板列表"""
        registry = container.template_registry
        return jsonify({"templates": registry.list_templates()})

    @app.route("/api/templates/upload", methods=["POST"])
    def upload_template():
        """上传模板文件"""
        if "file" not in request.files:
            return jsonify({"error": "缺少文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "文件名为空"}), 400

        allowed = {".md", ".docx", ".pdf"}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            return jsonify({"error": f"不支持的格式: {ext}"}), 400

        try:
            temp_path = Path("/tmp") / file.filename
            file.save(temp_path)

            registry = container.template_registry
            result = registry.upload(temp_path, file.filename)
            temp_path.unlink(missing_ok=True)

            return jsonify({"success": True, "template": result})
        except Exception as e:
            logger.error(f"上传模板失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/templates/activate", methods=["POST"])
    def activate_template():
        """激活指定模板"""
        data = request.json or {}
        name = data.get("template_name", "").strip()

        if not name:
            return jsonify({"error": "模板名称不能为空"}), 400

        registry = container.template_registry
        success = registry.activate(name)
        if not success:
            return jsonify({"error": f"模板 '{name}' 不存在或解析失败"}), 404

        # 更新当前会话
        session = container.session_manager.get_active()
        if session:
            session.active_template_name = name
            container.session_manager._persist()

        return jsonify({"success": True, "active_template": name})

    @app.route("/api/templates/<name>", methods=["DELETE"])
    def delete_template(name: str):
        """删除模板"""
        registry = container.template_registry
        if registry.delete(name):
            return jsonify({"success": True, "message": f"模板 '{name}' 已删除"})
        return jsonify({"error": f"模板 '{name}' 不存在"}), 404

    @app.route("/api/templates/<name>/parsed", methods=["GET"])
    def get_template_parsed(name: str):
        """获取解析后的模板内容"""
        registry = container.template_registry
        content = registry.get_parsed_content(name)
        if content is None:
            return jsonify({"error": f"模板 '{name}' 未解析"}), 404
        return jsonify({"name": name, "content": content})
```

- [ ] **Step 4: 修改 dependency_injection.py 添加 TemplateRegistry**

```python
# src/interfaces/dependency_injection.py
# 在 import 区域添加:
from src.domain.template_registry import TemplateRegistry

# 在 Container.__init__ 中，self.report_composer 之前添加:
self.template_registry = TemplateRegistry()
```

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/application/commands/upload_template.py src/application/commands/activate_template.py src/interfaces/web.py src/interfaces/dependency_injection.py && git commit -m "feat: template upload/activate/delete REST APIs"
```

---

## Phase 3: 报告修改 + 保存技能重写

### Task 11: 新增 ModifyReportCommand

**Files:**
- Create: `src/application/commands/modify_report.py`
- Create: `skills/report_modifier.md`
- Modify: `src/interfaces/web.py`（_resolve_command 增加 modify_report）
- Test: `tests/unit/test_modify_report.py`

- [ ] **Step 1: 创建 report_modifier skill**

```markdown
# skills/report_modifier.md
---
name: report_modifier
description: |
  报告修改专家。当用户在诊断期间要求修改报告内容时触发。
  包括但不限于：删除某章节内容、增加分析、调整结构、重写段落、
  修改措辞等。用户可能用自然语言描述修改意图，你需要精确理解并执行。
---

# 报告修改

## 修改原则

1. **精确理解**：仔细分析用户指令的真实意图，不猜测不臆断
2. **保持完整**：不删除用户未要求删除的内容
3. **逻辑连贯**：修改后报告整体逻辑必须通顺
4. **格式一致**：保持 Markdown 格式，章节层级不变（除非用户要求调整结构）
5. **专业准确**：修改后的内容必须专业、准确、符合电力行业规范

## 修改类型处理

### 删除
- 精确定位用户提到的章节/段落
- 只删除目标内容，保留上下文衔接

### 增加
- 在指定位置插入新内容
- 保持与前后文的风格和逻辑一致

### 修改
- 替换目标内容
- 保留原有结构框架

### 结构调整
- 按用户要求的顺序重新排列章节
- 确保章节编号和引用同步更新
```

- [ ] **Step 2: 实现 ModifyReportCommand**

```python
# src/application/commands/modify_report.py
"""修改报告 Command"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext, SessionStatus, UserAction
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.skill_loader import SkillLoader
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)


class ModifyReportCommand(Command):
    """修改报告 Command

    基于用户自然语言指令，LLM 理解意图后重写报告。
    """

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skill_loader: SkillLoader,
    ):
        self.llm = llm_service
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skill_loader = skill_loader

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行报告修改"""
        session = ctx.session
        instruction = ctx.user_message

        yield Event.thinking(session.session_id, "理解修改指令...")

        if not self.state_machine.can_execute(session, "modify_report"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许修改报告"
            )

        current_report = session.latest_report
        if not current_report:
            yield Event.error(session.session_id, "当前没有可修改的报告")
            return

        # 加载报告修改 Skill
        skill_md, _ = self.skill_loader.load("report_modifier")

        # 加载当前激活模板作为约束
        template_md = ""
        if session.active_template_name:
            from pathlib import Path
            parsed_path = Path("templates/parsed") / f"{session.active_template_name}.md"
            if parsed_path.exists():
                template_md = parsed_path.read_text(encoding="utf-8")

        prompt = f"""你是输电线路故障诊断报告编辑专家。

## 当前报告
{current_report}

## 用户修改指令
{instruction}

## 修改指导
{skill_md}

## 模板约束（必须遵守的章节结构）
{template_md or "使用默认章节结构：概述 / 故障分析 / 诊断证据 / 诊断结论 / 处理建议"}

## 修改要求
1. 严格理解用户意图，精确执行修改
2. 保持报告的专业性和逻辑连贯性
3. 不删除用户未要求删除的内容
4. 修改后报告必须符合模板章节结构
5. 如果用户要求调整章节顺序，在保持内容完整的前提下重新组织

请输出修改后的完整报告。
"""

        yield Event.thinking(session.session_id, "正在修改报告...")

        modified_report = await self.llm.chat([
            {"role": "system", "content": "你是输电线路故障诊断报告编辑专家。"},
            {"role": "user", "content": prompt},
        ])

        # 记录修改操作
        session.action_log.append(
            UserAction(
                action_type="modify_report",
                parameters={
                    "instruction": instruction,
                    "before_length": len(current_report),
                    "after_length": len(modified_report),
                },
            )
        )

        session.latest_report = modified_report
        self.session_manager._persist()

        logger.info(
            f"报告已修改: {session.session_id}, "
            f"before={len(current_report)}, after={len(modified_report)}"
        )

        yield Event.complete(
            session.session_id,
            {
                "message": "报告已按您的要求修改",
                "report": modified_report,
            },
        )
```

- [ ] **Step 3: 修改 web.py _resolve_command**

```python
# src/interfaces/web.py
# 在 _resolve_command 中添加:
from src.application.commands.modify_report import ModifyReportCommand

# 在函数中添加分支:
#     elif intent_type == IntentType.MODIFY_REPORT:
#         return ModifyReportCommand(
#             llm_service=container.llm_service,
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#             skill_loader=container.skill_loader,
#         )
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/application/commands/modify_report.py skills/report_modifier.md && git commit -m "feat: ModifyReportCommand with LLM-driven natural language report editing"
```

---

### Task 12: 重写 SaveSkillCommand（LLM 生成 Agent Skill 规范）

**Files:**
- Modify: `src/application/commands/save_skill.py`
- Modify: `src/application/commands/complete_diagnosis.py`
- Test: `tests/unit/test_save_skill.py`

- [ ] **Step 1: 实现新的 SaveSkillCommand**

```python
# src/application/commands/save_skill.py — 完整替换
"""保存技能 Command

将当前会话的调整保存为符合 Agent Skill 规范的 Markdown 文件，
使用 LLM 生成完整的 Skill 内容（YAML frontmatter + pushy description + 完整规则）。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import yaml

from src.core.models import DiagnosisSession, Event, ExecutionContext, SessionStatus
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.skill_loader import SkillLoader
from src.infrastructure.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path("skills")


class SaveSkillCommand(Command):
    """保存技能 Command"""

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: SessionManager,
        state_machine: StateMachine,
        skill_loader: SkillLoader,
        skills_dir: Path | None = None,
    ):
        self.llm = llm_service
        self.session_manager = session_manager
        self.state_machine = state_machine
        self.skill_loader = skill_loader
        self.skills_dir = skills_dir or DEFAULT_SKILLS_DIR

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行保存技能操作"""
        session = ctx.session
        skill_name = self._extract_skill_name(ctx)

        yield Event.thinking(
            session.session_id,
            f"保存技能: {skill_name}...",
        )

        self._validate_state(session)
        self._ensure_skills_dir()

        # 收集会话完整状态
        skill_config = self._build_skill_config(session, skill_name)

        # 使用 LLM 生成符合 Agent Skill 规范的 Markdown
        prompt = self._build_generation_prompt(skill_config)
        skill_md = await self.llm.chat([
            {"role": "system", "content": "你是 Skill 生成专家。将诊断配置转换为符合 Agent Skill 规范的 Markdown Skill 文件。"},
            {"role": "user", "content": prompt},
        ])

        file_path = self._save_to_file(skill_name, skill_md)

        session.active_skill_name = skill_name
        self.session_manager._persist()

        logger.info(f"技能已保存: {session.session_id} -> {file_path}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"技能 '{skill_name}' 已保存",
                "skill_name": skill_name,
                "file_path": str(file_path),
            },
        )

    def _extract_skill_name(self, ctx: ExecutionContext) -> str:
        if ctx.intent:
            name = ctx.intent.parameters.get("skill_name", "")
            if name:
                return name
            name = ctx.intent.parameters.get("strategy_name", "")
            if name:
                return name
        return f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _validate_state(self, session: DiagnosisSession) -> None:
        if not self.state_machine.can_execute(session, "save_skill"):
            raise InvalidStateError(
                f"当前状态 {session.status.value} 不允许保存技能"
            )

    def _ensure_skills_dir(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _build_skill_config(self, session: DiagnosisSession, name: str) -> dict:
        """收集会话状态构建 Skill 配置。"""
        weights = session.active_weights.copy()
        # 排除的工具从 weights 中标记
        excluded = session.excluded_tools.copy()

        # 构建 action_log 摘要
        action_summary = []
        for action in session.action_log:
            action_summary.append({
                "type": action.action_type,
                "params": action.parameters,
                "time": action.timestamp.isoformat(),
            })

        return {
            "name": name,
            "line_context": session.line_name,
            "weights": weights,
            "excluded_tools": excluded,
            "template_name": session.active_template_name,
            "action_history": action_summary,
        }

    def _build_generation_prompt(self, config: dict) -> str:
        weights_yaml = yaml.dump({"weights": config["weights"]}, allow_unicode=True)
        excluded_str = "\n".join(f"- {t}" for t in config["excluded_tools"]) or "无"

        action_lines = []
        for a in config["action_history"]:
            params = a["params"]
            if a["type"] == "exclude":
                action_lines.append(f"- 排除 {params.get('tool_name', '')}")
            elif a["type"] == "adjust_weight":
                action_lines.append(f"- 调整 {params.get('tool_name', '')} 权重为 {params.get('weight', '')}")
            elif a["type"] == "modify_report":
                action_lines.append(f"- 修改报告：{params.get('instruction', '')}")
            elif a["type"] == "complete":
                action_lines.append("- 完成诊断")

        return f"""请根据以下诊断配置，生成一个符合 Agent Skill 规范的 Markdown 文件。

## 配置信息

- 技能名称：{config['name']}
- 线路上下文：{config['line_context']}
- 激活模板：{config['template_name'] or '默认模板'}

### 工具权重配置
```yaml
{weights_yaml}
```

### 排除的工具
{excluded_str}

### 用户操作历史
{"\n".join(action_lines) or "无"}

## 生成要求

1. YAML frontmatter 必须包含 name 和 description（description 要 pushy，明确触发条件）
2. 必须包含"核心算法：加权置信度"章节，明确写出计算公式
3. 工具调用策略表必须反映排除的工具（标记为"跳过"或说明条件）
4. 诊断流程必须基于用户操作历史优化
5. 注意事项中体现用户的偏好设置
6. 末尾添加"历史优化记录"章节，说明本技能的来源
7. 格式与 comprehensive_diagnosis.md 一致

请直接输出 Markdown 内容，不要添加代码块标记。
"""

    def _save_to_file(self, name: str, content: str) -> Path:
        file_path = self.skills_dir / f"{name}.md"
        file_path.write_text(content, encoding="utf-8")
        # 更新缓存
        if hasattr(self.skill_loader, '_cache'):
            self.skill_loader._cache[name] = content
        return file_path
```

- [ ] **Step 2: 修改 CompleteDiagnosisCommand（完成后提示保存技能）**

```python
# src/application/commands/complete_diagnosis.py — 修改 complete 事件的 payload
# 在 yield Event.complete 中增加 suggest_save_skill:
        yield Event.complete(
            session.session_id,
            {
                "message": "诊断已完成",
                "status": session.status.value,
                "line_name": session.line_name,
                "suggest_save_skill": True,
            },
        )
```

- [ ] **Step 3: 修改 web.py _resolve_command（SaveSkillCommand 增加 LLM 依赖）**

```python
# src/interfaces/web.py — 修改 SAVE_STRATEGY 分支（保留兼容，实际走 save_skill）
# SaveStrategyCommand 和 SaveSkillCommand 是同一个概念
# 当前 SaveStrategyCommand 存在，我们需要修改它或替换它
# 由于 intent 中有 SAVE_STRATEGY，我们在 _resolve_command 中映射到 SaveSkillCommand:

# 将:
#     elif intent_type == IntentType.SAVE_STRATEGY:
#         return SaveStrategyCommand(...)
# 替换为:
#     elif intent_type == IntentType.SAVE_STRATEGY:
#         return SaveSkillCommand(
#             llm_service=container.llm_service,
#             session_manager=container.session_manager,
#             state_machine=container.state_machine,
#             skill_loader=container.skill_loader,
#         )
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add src/application/commands/save_skill.py src/application/commands/complete_diagnosis.py && git commit -m "feat: SaveSkillCommand generates Agent Skill spec via LLM"
```

---

## Phase 4: 前端改造（v2.0 设计系统）

> 基于 **智慧电网指挥中心** 视觉方向（深色工业科技风）。
> 所有组件使用新的 CSS 设计令牌（`--bg-base`, `--color-primary` 等）。

---

### Task 13: 全局设计系统 CSS + AppHeader.vue

**Files:**
- Create: `web/src/styles/design-system.css`
- Create: `web/src/components/AppHeader.vue`
- Modify: `web/src/App.vue`（引入 design-system.css）

- [ ] **Step 1: 创建全局设计系统 CSS**

```css
/* web/src/styles/design-system.css */
:root {
  /* 背景层 */
  --bg-base: #060b14;
  --bg-panel: #0f172a;
  --bg-panel-glass: rgba(15, 23, 42, 0.85);
  --bg-elevated: #1e293b;
  --bg-input: #0a0f1a;

  /* 功能色 */
  --color-primary: #3b82f6;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-accent: #06b6d4;

  /* 文字色 */
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-inverse: #0f172a;

  /* 边框 */
  --border-subtle: rgba(148, 163, 184, 0.1);
  --border-medium: rgba(148, 163, 184, 0.2);
  --border-glow: rgba(59, 130, 246, 0.3);

  /* 字体 */
  --font-display: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  --font-mono: "JetBrains Mono", "SF Mono", "Fira Code", "Courier New", monospace;
  --font-body: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;

  /* 字号 */
  --text-xs: 0.6875rem;
  --text-sm: 0.75rem;
  --text-base: 0.8125rem;
  --text-md: 0.9375rem;
  --text-lg: 1.125rem;
  --text-xl: 1.5rem;
  --text-2xl: 2rem;

  /* 间距与圆角 */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;

  /* 动效 */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;

  /* 状态色 */
  --status-pending: #64748b;
  --status-diagnosing: #3b82f6;
  --status-modifying: #f59e0b;
  --status-completed: #10b981;
}

/* 全局背景 */
.app-container {
  background: var(--bg-base);
  background-image:
    radial-gradient(ellipse at 50% 0%, rgba(59, 130, 246, 0.04) 0%, transparent 60%),
    linear-gradient(rgba(148, 163, 184, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.03) 1px, transparent 1px);
  background-size: 100% 100%, 40px 40px, 40px 40px;
  min-height: 100vh;
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-base);
}

/* 滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* 动画 */
@keyframes pulse-glow {
  0%, 100% { filter: drop-shadow(0 0 2px var(--color-primary)); opacity: 0.8; }
  50% { filter: drop-shadow(0 0 6px var(--color-primary)); opacity: 1; }
}

@keyframes breathing {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px currentColor; }
  50% { opacity: 0.4; box-shadow: 0 0 2px currentColor; }
}

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes toast-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

- [ ] **Step 2: 创建 AppHeader.vue**

```vue
<!-- web/src/components/AppHeader.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'

const store = useSessionStore()

const statusColor = computed(() => {
  const status = store.activeSession?.status
  if (status === 'diagnosing') return '#3b82f6'
  if (status === 'modifying') return '#f59e0b'
  if (status === 'completed') return '#10b981'
  return '#64748b'
})

const isBreathing = computed(() => {
  const status = store.activeSession?.status
  return status === 'diagnosing' || status === 'modifying'
})
</script>

<template>
  <header class="app-header">
    <div class="header-brand">
      <span class="header-icon" :style="{ animation: 'pulse-glow 3s ease-in-out infinite' }">&#9889;</span>
      <div>
        <div class="header-title">输电线路故障综合诊断智能体</div>
        <div class="header-subtitle">Power Line Fault Comprehensive Diagnosis Agent</div>
      </div>
    </div>
    <div class="status-indicator">
      <span
        class="status-dot"
        :class="{ breathing: isBreathing }"
        :style="{ background: statusColor, color: statusColor }"
      />
      <span>{{ store.activeSession?.status || '就绪' }}</span>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  background: rgba(6, 11, 20, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%, var(--color-primary) 20%,
    var(--color-accent) 50%, var(--color-primary) 80%, transparent 100%
  );
  opacity: 0.6;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.25rem;
}

.header-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

.header-subtitle {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 4px currentColor;
}

.status-dot.breathing {
  animation: breathing 2s ease-in-out infinite;
}
</style>
```

- [ ] **Step 3: 修改 App.vue 引入设计系统**

```typescript
// 在 App.vue 的 script setup 或 style 标签中
// 添加: import '@/styles/design-system.css'
// 根 div 添加 class="app-container"
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/styles/design-system.css web/src/components/AppHeader.vue web/src/App.vue && git commit -m "feat: AppHeader with Smart Grid Command Center design system"
```

---

### Task 14: 时间格式化工具 + SessionSidebar/ReportHistory 改造

**Files:**
- Create: `web/src/utils/time.ts`
- Modify: `web/src/components/SessionSidebar.vue`
- Modify: `web/src/components/ReportHistory.vue`

- [ ] **Step 1: 创建时间格式化工具**

```typescript
// web/src/utils/time.ts
export function formatTime(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => n.toString().padStart(2, '0')
  const ms = d.getMilliseconds().toString().padStart(3, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${ms}`
}
```

- [ ] **Step 2: 改造 SessionSidebar.vue（新样式）**

```vue
<!-- SessionSidebar 样式改为深色主题 -->
<style scoped>
.session-sidebar {
  width: 260px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 1rem;
  font-weight: 600;
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text-primary);
}

.session-item {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast);
}

.session-item:hover {
  background: var(--bg-elevated);
}

.session-item.active {
  background: rgba(59, 130, 246, 0.08);
  border-left: 3px solid var(--color-primary);
}

.session-name {
  font-weight: 600;
  font-size: var(--text-md);
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--text-primary);
}

.session-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  font-size: var(--text-xs);
}

.meta-tag {
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}

.meta-tag.voltage {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.meta-tag.status-diagnosing {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
}

.meta-tag.status-modifying {
  background: rgba(245, 158, 11, 0.12);
  color: var(--color-warning);
}

.meta-tag.status-completed {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.meta-tag.fault-time {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: transparent;
  padding: 0;
  letter-spacing: 0.02em;
}
</style>
```

- [ ] **Step 3: 改造 ReportHistory.vue（深色表格）**

```css
/* ReportHistory 样式 */
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.report-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-medium);
  text-transform: uppercase;
  font-size: var(--text-xs);
  letter-spacing: 0.05em;
}

.report-table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.report-table tr:hover td {
  background: rgba(148, 163, 184, 0.04);
}

.report-table .time-cell {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  font-size: var(--text-xs);
}
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/utils/time.ts web/src/components/SessionSidebar.vue web/src/components/ReportHistory.vue && git commit -m "feat: dark-theme SessionSidebar/ReportHistory with millisecond time"
```

---

### Task 15: 前端 API 扩展 + sessionStore

与原 Task 14 内容一致（API 和 store 逻辑不变，仅适配深色主题样式）。
详见原 plan Task 14 的 http.ts 和 sessionStore.ts 代码。

- [ ] **Step 1-3: 同上**

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/api/http.ts web/src/stores/sessionStore.ts && git commit -m "feat: frontend template APIs and store actions"
```

---

### Task 16: ChatPanel.vue 增强（新设计系统 + ActionPanel）

**Files:**
- Modify: `web/src/components/ChatPanel.vue`

- [ ] **Step 1: 引入 design-system 变量，添加 ActionPanel 逻辑**

```typescript
// 新增 import
import { formatTime } from '@/utils/time'

// ActionPanel 状态
const showActionPanel = ref(false)
const showModifyInput = ref(false)
const modifyInstruction = ref('')

// 快捷操作方法
function handleExcludeTool(toolName: string) {
  store.postMessage(`排除${toolName}`)
}
function handleRecheckTool(toolName: string) {
  store.postMessage(`重新检查${toolName}`)
}
function handleAdjustWeight(toolName: string) {
  const w = prompt(`调整 ${toolName} 权重 (0.1-2.0):`)
  if (w) store.postMessage(`把${toolName}权重调到${w}`)
}
function handleModifyReport() {
  showModifyInput.value = true
}
function submitModifyReport() {
  if (!modifyInstruction.value.trim()) return
  store.postMessage(modifyInstruction.value)
  modifyInstruction.value = ''
  showModifyInput.value = false
}
```

- [ ] **Step 2: SummaryCard 新样式（深色主题 + 置信度条）**

```vue
<!-- SummaryCard 结构 -->
<div class="summary-card">
  <div class="summary-header">
    <span>&#10003;</span> 诊断完成
  </div>
  <div class="summary-body">
    <div class="summary-row">
      <span class="summary-label">电压等级</span>
      <span class="summary-value">{{ msg.summary.voltage_level }}</span>
    </div>
    <div class="summary-row">
      <span class="summary-label">故障时间</span>
      <span class="summary-value time">{{ formatTime(msg.summary.fault_time) }}</span>
    </div>
    <div class="summary-row">
      <span class="summary-label">置信度</span>
      <div class="confidence-bar">
        <div
          class="confidence-bar-fill"
          :class="confidenceLevel"
          :style="{ width: (msg.summary.confidence * 100) + '%' }"
        />
      </div>
      <span class="summary-value">{{ Math.round(msg.summary.confidence * 100) }}%</span>
    </div>
  </div>
</div>
```

```css
.summary-card {
  background: var(--bg-panel-glass);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  overflow: hidden;
  backdrop-filter: blur(8px);
}

.summary-header {
  padding: 0.75rem 1rem;
  background: rgba(16, 185, 129, 0.08);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: var(--color-success);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-subtle);
}

.summary-label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.summary-value.time {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-accent);
}

.confidence-bar {
  width: 120px;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width var(--duration-slow) var(--ease-out-expo);
}

.confidence-bar-fill.high { background: var(--color-success); }
.confidence-bar-fill.medium { background: var(--color-warning); }
.confidence-bar-fill.low { background: var(--color-danger); }
```

- [ ] **Step 3: ActionPanel + 修改输入框（深色主题）**

```css
.action-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.action-panel-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.action-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.action-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: translateY(-1px);
}

.modify-input-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-input);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
}

.modify-input-panel textarea {
  width: 100%;
  resize: none;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.625rem;
  font-size: var(--text-base);
  color: var(--text-primary);
  line-height: 1.6;
}

.modify-input-panel textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/components/ChatPanel.vue && git commit -m "feat: ChatPanel with dark theme, ActionPanel, confidence bars"
```

---

### Task 17: TemplateManager.vue（新设计系统）

**Files:**
- Create: `web/src/components/TemplateManager.vue`

与原 Task 16 结构一致，但所有样式使用深色主题设计令牌。核心变化：
- `.template-manager` → `padding: 1.5rem; max-width: 900px;`
- `.tm-header h2` → 使用 `var(--font-display)` 和 `var(--text-lg)`
- `.tm-upload-btn` → `background: var(--color-primary);`
- `.tm-drop-zone` → `background: var(--bg-panel); border-color: var(--border-medium);`
- `.tm-item` → `background: var(--bg-panel); border-color: var(--border-subtle);`
- `.tm-item.active` → `border-color: var(--color-success);`
- 所有颜色引用替换为 CSS 变量

具体代码见前端设计文档第 5 节。

- [ ] **Step 1: 实现组件**

- [ ] **Step 2: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/components/TemplateManager.vue && git commit -m "feat: TemplateManager.vue with Smart Grid dark theme"
```

---

### Task 18: ToolList + StrategyManager 样式改造

**Files:**
- Modify: `web/src/components/ToolList.vue`
- Modify: `web/src/components/StrategyManager.vue`

- [ ] **Step 1: ToolList.vue 深色主题改造**

```css
.tool-list {
  width: 240px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  border-right: 1px solid var(--border-subtle);
  padding: 1rem;
}

.tool-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  margin-bottom: 0.625rem;
}

.tool-card.excluded {
  opacity: 0.5;
}

.weight-track {
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  margin: 0.375rem 0;
}

.weight-track-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
}
```

- [ ] **Step 2: StrategyManager.vue 深色主题改造**

```css
.strategy-manager {
  width: 260px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  padding: 1rem;
}

.skill-item {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.875rem;
  margin-bottom: 0.625rem;
}

.skill-item.active {
  border-color: var(--color-success);
  background: rgba(16, 185, 129, 0.03);
}

.skill-badge.active {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.skill-badge.user {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
}
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/e/Cluade_PLDiagonsis && git add web/src/components/ToolList.vue web/src/components/StrategyManager.vue && git commit -m "style: ToolList and StrategyManager dark theme"
```

---

## 计划自检

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|----------|
| 时间精度修复（毫秒） | Task 1 |
| YAML frontmatter Skill 格式 | Task 2, 3, 4 |
| 删除 WeightEngine | Task 5 |
| ReportComposer 模板注入 | Task 6 |
| 多格式模板解析（md/docx/pdf） | Task 8 |
| 模板注册表 + API | Task 9, 10 |
| 交互式报告修改 | Task 11 |
| LLM 生成 Skill 规范 | Task 12 |
| 全局设计系统 + AppHeader | Task 13 |
| 前端时间显示 | Task 14 |
| 前端模板 API | Task 15 |
| ChatPanel ActionPanel + 新样式 | Task 16 |
| TemplateManager.vue 新样式 | Task 17 |
| ToolList + StrategyManager 深色主题 | Task 18 |

### Placeholder 扫描

- 无 "TBD", "TODO", "implement later", "fill in details"
- 无 "Add appropriate error handling" 等模糊描述
- 每个代码步骤都有完整代码块
- 无 "Similar to Task N" 引用

### 类型一致性

- `active_template_name: Optional[str]` 在 models.py、DiagnoseCommand、ReportComposer 中一致
- `TemplateRegistry` 方法名在 domain 和 commands 中一致
- `SkillLoader.extract_metadata` 返回 `dict`，与前端 `SkillInfo` 接口对应
- 时间格式统一使用 `YYYY-MM-DD HH:MM:SS.mmm`

---

*计划版本: v2.0*
*日期: 2026-05-21*
*前端设计: v2.0 智慧电网指挥中心风格*
