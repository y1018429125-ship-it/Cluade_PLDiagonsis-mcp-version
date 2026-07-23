"""Tests for src/domain/session_manager.py — CRUD, reuse, weights, tool exclusion."""

from pathlib import Path

import pytest

from src.core.exceptions import SessionNotFoundError
from src.core.models import (
    DiagnosisSession,
    DiagnosisSummary,
    FaultContext,
    SessionStatus,
    UserAction,
)
from src.domain.session_manager import SessionManager
from src.domain.state_machine import StateMachine
from src.domain.template_registry import TemplateRegistry
from src.infrastructure.event_bus import EventBus


# ============================================================================
# create
# ============================================================================


def test_create_returns_session_with_id(session_manager: SessionManager) -> None:
    """create() returns a session with a generated id."""
    session = session_manager.create("220kV京西线")
    assert session.session_id.startswith("sess_")
    assert len(session.session_id) == 13


def test_create_normalizes_line_name(session_manager: SessionManager) -> None:
    """create() strips voltage prefix from line name."""
    session = session_manager.create("220kV京西线")
    assert session.line_name == "京西线"


def test_create_sets_pending_status(session_manager: SessionManager) -> None:
    """create() initializes status to PENDING."""
    session = session_manager.create("LineA")
    assert session.status == SessionStatus.PENDING


def test_create_makes_session_active(session_manager: SessionManager) -> None:
    """create() sets the new session as the active session."""
    session = session_manager.create("LineA")
    assert session_manager.get_active() == session


# ============================================================================
# get / get_active
# ============================================================================


def test_get_returns_existing_session(session_manager: SessionManager) -> None:
    """get() retrieves a previously created session."""
    created = session_manager.create("LineA")
    fetched = session_manager.get(created.session_id)
    assert fetched.session_id == created.session_id


def test_get_raises_when_session_missing(session_manager: SessionManager) -> None:
    """get() raises SessionNotFoundError for unknown ids."""
    with pytest.raises(SessionNotFoundError) as exc_info:
        session_manager.get("sess_nonexistent")
    assert "不存在" in str(exc_info.value)


def test_get_active_returns_none_when_empty(session_manager: SessionManager) -> None:
    """get_active() returns None before any session is created."""
    assert session_manager.get_active() is None


# ============================================================================
# get_or_create — reuse semantics
# ============================================================================


def test_get_or_create_reuses_same_line(session_manager: SessionManager) -> None:
    """get_or_create() returns the same session for the same line."""
    first = session_manager.create("220kV京西线")
    second = session_manager.get_or_create("220kV京西线")
    assert first.session_id == second.session_id


def test_get_or_create_reuses_with_different_voltage_prefix(session_manager: SessionManager) -> None:
    """get_or_create() matches lines regardless of voltage prefix."""
    first = session_manager.create("220kV京西线")
    second = session_manager.get_or_create("110kV京西线")
    assert first.session_id == second.session_id


def test_get_or_create_creates_new_for_different_line(session_manager: SessionManager) -> None:
    """get_or_create() creates a new session for a different line."""
    first = session_manager.create("京西线")
    second = session_manager.get_or_create("武昌线")
    assert first.session_id != second.session_id


def test_get_or_create_creates_new_when_completed(session_manager: SessionManager) -> None:
    """get_or_create() creates a new session when the old one is COMPLETED."""
    first = session_manager.create("京西线")
    session_manager.transition(first.session_id, SessionStatus.DIAGNOSING)
    session_manager.transition(first.session_id, SessionStatus.MODIFYING)
    session_manager.transition(first.session_id, SessionStatus.COMPLETED)

    second = session_manager.get_or_create("京西线")
    assert first.session_id != second.session_id


def test_get_or_create_sets_active(session_manager: SessionManager) -> None:
    """get_or_create() switches active session to the reused one."""
    first = session_manager.create("京西线")
    session_manager.create("武昌线")
    reused = session_manager.get_or_create("京西线")
    assert session_manager.get_active() == reused


# ============================================================================
# list_sessions / switch_active
# ============================================================================


def test_list_sessions_returns_all(session_manager: SessionManager) -> None:
    """list_sessions() returns every created session."""
    session_manager.create("LineA")
    session_manager.create("LineB")
    assert len(session_manager.list_sessions()) == 2


def test_switch_active_changes_active_session(session_manager: SessionManager) -> None:
    """switch_active() updates the active session pointer."""
    s1 = session_manager.create("LineA")
    s2 = session_manager.create("LineB")
    session_manager.switch_active(s1.session_id)
    assert session_manager.get_active() == s1


def test_switch_active_raises_for_unknown(session_manager: SessionManager) -> None:
    """switch_active() raises SessionNotFoundError for invalid ids."""
    with pytest.raises(SessionNotFoundError):
        session_manager.switch_active("sess_bad")


# ============================================================================
# transition delegation
# ============================================================================


def test_transition_delegates_to_state_machine(session_manager: SessionManager) -> None:
    """transition() mutates session status via the state machine."""
    session = session_manager.create("LineA")
    session_manager.transition(session.session_id, SessionStatus.DIAGNOSING)
    assert session.status == SessionStatus.DIAGNOSING


# ============================================================================
# add_summary
# ============================================================================


def test_add_summary_appends_and_sets_current(session_manager: SessionManager) -> None:
    """add_summary() appends to summaries and sets current_summary."""
    session = session_manager.create("LineA")
    ctx = FaultContext(line_id="L1", line_name="LineA")
    summary = DiagnosisSummary(fault_context=ctx)

    session_manager.add_summary(session.session_id, summary)

    assert len(session.summaries) == 1
    assert session.current_summary == summary


# ============================================================================
# update_weights
# ============================================================================


def test_update_weights_merges_into_active_weights(session_manager: SessionManager) -> None:
    """update_weights() overlays new values onto active_weights."""
    session = session_manager.create("LineA")
    session_manager.update_weights(session.session_id, {"LightningDiagnosisTool": 1.5})
    assert session.active_weights["LightningDiagnosisTool"] == 1.5


def test_update_weights_preserves_untouched_keys(session_manager: SessionManager) -> None:
    """update_weights() leaves unspecified keys unchanged."""
    session = session_manager.create("LineA")
    old_wind = session.active_weights["WindDiagnosisTool"]
    session_manager.update_weights(session.session_id, {"LightningDiagnosisTool": 1.5})
    assert session.active_weights["WindDiagnosisTool"] == old_wind


def test_update_weights_updates_timestamp(session_manager: SessionManager) -> None:
    """update_weights() refreshes updated_at."""
    from datetime import datetime

    session = session_manager.create("LineA")
    old_time = session.updated_at
    session_manager.update_weights(session.session_id, {"LightningDiagnosisTool": 1.5})
    assert session.updated_at >= old_time


# ============================================================================
# exclude_tool / include_tool
# ============================================================================


def test_exclude_tool_adds_to_excluded_list(session_manager: SessionManager) -> None:
    """exclude_tool() appends the tool name to excluded_tools."""
    session = session_manager.create("LineA")
    session_manager.exclude_tool(session.session_id, "ToolA")
    assert "ToolA" in session.excluded_tools


def test_exclude_tool_is_idempotent(session_manager: SessionManager) -> None:
    """exclude_tool() does not duplicate entries."""
    session = session_manager.create("LineA")
    session_manager.exclude_tool(session.session_id, "ToolA")
    session_manager.exclude_tool(session.session_id, "ToolA")
    assert session.excluded_tools.count("ToolA") == 1


def test_include_tool_removes_from_excluded_list(session_manager: SessionManager) -> None:
    """include_tool() removes the tool name from excluded_tools."""
    session = session_manager.create("LineA")
    session_manager.exclude_tool(session.session_id, "ToolA")
    session_manager.include_tool(session.session_id, "ToolA")
    assert "ToolA" not in session.excluded_tools


def test_include_tool_is_idempotent(session_manager: SessionManager) -> None:
    """include_tool() is safe when tool was never excluded."""
    session = session_manager.create("LineA")
    session_manager.include_tool(session.session_id, "ToolA")
    assert "ToolA" not in session.excluded_tools


def test_exclude_and_include_update_timestamp(session_manager: SessionManager) -> None:
    """Both exclude_tool and include_tool refresh updated_at."""
    session = session_manager.create("LineA")
    t1 = session.updated_at
    session_manager.exclude_tool(session.session_id, "ToolA")
    t2 = session.updated_at
    session_manager.include_tool(session.session_id, "ToolA")
    t3 = session.updated_at
    assert t2 >= t1
    assert t3 >= t2


# ============================================================================
# add_rechecked
# ============================================================================


def test_add_rechecked_appends_once(session_manager: SessionManager) -> None:
    """add_rechecked() records the tool name without duplicates."""
    session = session_manager.create("LineA")
    session_manager.add_rechecked(session.session_id, "ToolA")
    session_manager.add_rechecked(session.session_id, "ToolA")
    assert session.rechecked_tools == ["ToolA"]


# ============================================================================
# template inheritance
# ============================================================================


def test_create_inherits_active_template(session_manager: SessionManager) -> None:
    """create() should inherit the globally activated template."""
    from src.domain.template_registry import UPLOADS_DIR, PARSED_DIR

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / ".active").write_text("my_template", encoding="utf-8")
    (PARSED_DIR / "my_template.md").write_text("# Test Template\n", encoding="utf-8")

    try:
        session = session_manager.create("京西线")
        assert session.active_template_name == "my_template"
    finally:
        # Clean up
        active_file = UPLOADS_DIR / ".active"
        if active_file.exists():
            active_file.unlink()
        parsed_file = PARSED_DIR / "my_template.md"
        if parsed_file.exists():
            parsed_file.unlink()


def test_create_auto_activates_first_parsed_template(session_manager: SessionManager) -> None:
    """create() auto-activates the first parsed template when no .active file exists."""
    from src.domain.template_registry import UPLOADS_DIR, PARSED_DIR

    active_file = UPLOADS_DIR / ".active"
    if active_file.exists():
        active_file.unlink()

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    # 创建测试模板文件（000_ 前缀确保按字母排序排在第一位）
    test_md = PARSED_DIR / "000_test_template.md"
    test_md.write_text("# Test\n", encoding="utf-8")

    try:
        session = session_manager.create("京西线")
        assert session.active_template_name == "000_test_template"
    finally:
        if test_md.exists():
            test_md.unlink()


def test_create_allows_no_active_template_when_no_parsed(session_manager: SessionManager) -> None:
    """create() leaves active_template_name as None when no parsed templates exist."""
    from src.domain.template_registry import UPLOADS_DIR, PARSED_DIR

    active_file = UPLOADS_DIR / ".active"
    if active_file.exists():
        active_file.unlink()

    # 临时移走所有解析模板，确保目录为空
    moved: list[tuple[Path, Path]] = []
    for p in list(PARSED_DIR.glob("*.md")):
        dest = p.parent / f"{p.name}.tmpbak"
        p.rename(dest)
        moved.append((dest, p))

    try:
        session = session_manager.create("京西线")
        assert session.active_template_name is None
    finally:
        for dest, orig in moved:
            if dest.exists():
                dest.rename(orig)
