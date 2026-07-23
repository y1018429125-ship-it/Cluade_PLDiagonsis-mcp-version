# Fix Template Inheritance and Skill Report Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion.

**Goal:** Fix two bugs: (1) new diagnosis sessions don't inherit the globally activated template, and (2) saved skills don't encode report modification rules as executable Agent Skill instructions.

**Architecture:** Align with Anthropic skill-creator spec: skills are self-contained imperative instructions. Remove the fragile `# 报告定制` extraction mechanism; instead, embed report rules directly in the skill body. Ensure new sessions inherit the active template from TemplateRegistry.

**Tech Stack:** Python 3.10+, pytest, Pydantic

---

## File Map

| File | Responsibility | Action |
|------|---------------|--------|
| `src/domain/session_manager.py` | Creates new sessions, manages lifecycle | Modify `create()` to inherit active template |
| `src/application/commands/save_skill.py` | Generates skill markdown from session state | Rewrite prompt to generate proper Agent Skill with embedded report rules |
| `src/domain/report_composer.py` | Composes diagnosis report via LLM | Remove `# 报告定制` extraction; use full skill content |
| `src/domain/skill_loader.py` | Loads skill markdown files | Remove `extract_report_customization` method |
| `tests/unit/test_session_manager.py` | Tests session creation | Add test for template inheritance |
| `tests/unit/test_save_skill.py` | Tests skill generation | Add test for proper skill format |
| `tests/unit/test_report_composer.py` | Tests report composition | Update tests to verify full skill usage |

---

## Task 1: Fix Template Inheritance in SessionManager

**Files:**
- Modify: `src/domain/session_manager.py:59-85`
- Test: `tests/unit/test_session_manager.py`

### Step 1: Write failing test

```python
def test_create_session_inherits_active_template(event_bus, state_machine):
    """New sessions should inherit the globally activated template."""
    from src.domain.template_registry import TemplateRegistry
    registry = TemplateRegistry()
    # Create a fake parsed template
    from pathlib import Path
    Path("templates/parsed/test_template.md").parent.mkdir(parents=True, exist_ok=True)
    Path("templates/parsed/test_template.md").write_text("# Test Template\n")
    registry.activate("test_template")

    manager = SessionManager(event_bus, state_machine)
    session = manager.create("test_line")
    assert session.active_template_name == "test_template"
```

### Step 2: Run test (expect FAIL)

```bash
pytest tests/unit/test_session_manager.py::test_create_session_inherits_active_template -v
```

Expected: FAIL — `active_template_name` is None.

### Step 3: Fix SessionManager.create()

In `src/domain/session_manager.py`, after creating the session, check TemplateRegistry for active template:

```python
from src.domain.template_registry import TemplateRegistry

def create(self, line_name: str, fault_context: Optional[FaultContext] = None) -> DiagnosisSession:
    # ... existing code ...
    session = DiagnosisSession(...)
    session.active_skill_name = self._default_skill_name
    
    # Inherit globally active template
    try:
        registry = TemplateRegistry()
        active_template = registry.get_active()
        if active_template:
            session.active_template_name = active_template
    except Exception:
        pass  # Template registry failure should not block session creation
    
    # ... rest of existing code ...
```

### Step 4: Run test (expect PASS)

### Step 5: Commit

---

## Task 2: Rewrite SaveSkillCommand to Generate Proper Agent Skill

**Files:**
- Modify: `src/application/commands/save_skill.py`
- Test: `tests/unit/test_save_skill.py`

### Step 1: Write failing test

```python
async def test_save_skill_embeds_report_rules(mock_llm_service, session_manager, state_machine, skill_loader):
    """Saved skill must embed report modification rules as imperative instructions."""
    from src.application.commands.save_skill import SaveSkillCommand
    from src.core.models import ExecutionContext, DiagnosisSession, SessionStatus, UserAction
    
    cmd = SaveSkillCommand(mock_llm_service, session_manager, state_machine, skill_loader)
    session = session_manager.create("test_line")
    session.action_log.append(UserAction(action_type="exclude", parameters={"tool_name": "LightningDiagnosisTool"}))
    session.action_log.append(UserAction(action_type="modify_report", parameters={"instruction": "删除第三章"}))
    
    ctx = ExecutionContext(session=session, diagnosis_ctx=None, user_message="保存技能")
    
    events = []
    async for e in cmd.execute(ctx):
        events.append(e)
    
    # Check the prompt sent to LLM contains structured report rules
    prompt = mock_llm_service.chat.call_args[0][0][1]["content"]
    assert "删除第三章" in prompt
    assert "报告规则" in prompt or "report rules" in prompt
```

### Step 2: Run test (expect FAIL)

### Step 3: Rewrite SaveSkillCommand._build_generation_prompt()

Transform action history into structured imperative rules:

```python
def _build_generation_prompt(self, config: dict) -> str:
    # Build imperative rules from action history
    rules = []
    for a in config["action_history"]:
        params = a["params"]
        if a["type"] == "exclude":
            rules.append(f"- SKIP the {params.get('tool_name', '')} tool entirely in the diagnosis plan.")
        elif a["type"] == "adjust_weight":
            rules.append(f"- Use weight {params.get('weight', '')} for {params.get('tool_name', '')} when computing weighted confidence.")
        elif a["type"] == "modify_report":
            rules.append(f"- When composing the report: {params.get('instruction', '')}")
    
    # ... existing prompt structure but with imperative rules section ...
```

### Step 4: Run test (expect PASS)

### Step 5: Commit

---

## Task 3: ReportComposer Uses Full Skill Content

**Files:**
- Modify: `src/domain/report_composer.py`
- Test: `tests/unit/test_report_composer.py`

### Step 1: Write failing test

```python
async def test_compose_uses_full_skill_content(mock_llm_service, skill_loader):
    """ReportComposer should load full skill markdown, not extract a section."""
    from src.domain.report_composer import ReportComposer
    
    composer = ReportComposer(mock_llm_service, skill_loader)
    
    # Setup: save a skill with embedded report rules
    skill_content = """---
name: test_skill
description: test
---

# Diagnostic Rules

## Tool Strategy
- Skip LightningDiagnosisTool

## Report Rules
- Remove chapter 3 entirely
- Use template structure: overview / evidence / conclusion
"""
    skill_loader.save("test_skill", skill_content)
    
    outputs = {"ToolA": ToolOutput(tool_name="ToolA", structured_data={"confidence": 0.8})}
    result = await composer.compose(outputs, None, "sess_1", None, None, active_skill_name="test_skill")
    
    prompt = mock_llm_service.chat.call_args[0][0][1]["content"]
    assert "Remove chapter 3 entirely" in prompt
    assert "Skip LightningDiagnosisTool" in prompt
```

### Step 2: Run test (expect FAIL)

### Step 3: Modify ReportComposer.compose()

Remove `extract_report_customization` call. Load full skill content and include it in prompt:

```python
async def compose(self, tool_outputs, template, session_id, fault_context=None, action_log=None, weights=None, active_template_name=None, active_skill_name=None):
    template_md = self._load_template_md(active_template_name)
    
    # Load full skill content (self-contained instructions)
    skill_md = ""
    if self.skill_loader and active_skill_name:
        skill_md, _ = self.skill_loader.load(active_skill_name)
    
    prompt = self._build_prompt(tool_outputs, fault_context, action_log, weights, template_md, skill_md)
    # ...
```

Update `_build_prompt` to accept `skill_md` instead of `report_customization`.

### Step 4: Run test (expect PASS)

### Step 5: Commit

---

## Task 4: Remove extract_report_customization from SkillLoader

**Files:**
- Modify: `src/domain/skill_loader.py`

### Step 1: Delete method

Remove `extract_report_customization` method (lines 180-201).

### Step 2: Update tests

Remove any test that calls `extract_report_customization`.

### Step 3: Commit

---

## Task 5: Integration Test

### Step 1: Write end-to-end test

```python
async def test_full_flow_template_and_skill(event_bus, state_machine, mock_llm_service):
    """Full flow: activate template → create session → diagnose → save skill → verify skill has rules."""
    from src.domain.template_registry import TemplateRegistry
    from src.domain.session_manager import SessionManager
    from src.application.commands.save_skill import SaveSkillCommand
    from src.domain.skill_loader import SkillLoader
    from src.core.models import UserAction
    
    # Activate template
    registry = TemplateRegistry()
    Path("templates/parsed/my_template.md").parent.mkdir(parents=True, exist_ok=True)
    Path("templates/parsed/my_template.md").write_text("# My Template\n\n## Overview\n")
    registry.activate("my_template")
    
    # Create session — should inherit template
    manager = SessionManager(event_bus, state_machine)
    session = manager.create("test_line")
    assert session.active_template_name == "my_template"
    
    # Add report modification
    session.action_log.append(UserAction(action_type="modify_report", parameters={"instruction": "删除第三章"}))
    
    # Save skill
    skill_loader = SkillLoader()
    cmd = SaveSkillCommand(mock_llm_service, manager, state_machine, skill_loader)
    ctx = ExecutionContext(session=session, diagnosis_ctx=None, user_message="保存技能")
    
    async for e in cmd.execute(ctx):
        pass
    
    # Verify skill contains imperative rules
    skill_name = session.active_skill_name
    content, _ = skill_loader.load(skill_name)
    assert "删除第三章" in content
```

### Step 2: Run and fix any issues

### Step 3: Commit

---

## Verification Commands

```bash
# Run all affected tests
pytest tests/unit/test_session_manager.py tests/unit/test_save_skill.py tests/unit/test_report_composer.py -v

# Run with coverage
pytest tests/unit/test_session_manager.py tests/unit/test_save_skill.py tests/unit/test_report_composer.py --cov=src/domain/session_manager.py --cov=src/application/commands/save_skill.py --cov=src/domain/report_composer.py --cov=src/domain/skill_loader.py -v

# Run full test suite to ensure no regressions
pytest tests/ -v --tb=short
```
