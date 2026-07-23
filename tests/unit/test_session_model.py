"""Tests for DiagnosisSession model skill-related fields."""

import pytest
from src.core.models import DiagnosisSession


def test_session_has_included_tools():
    """Session should have included_tools field defaulting to empty list."""
    session = DiagnosisSession(session_id="test-1", line_name="LineA")
    assert hasattr(session, "included_tools")
    assert session.included_tools == []

    session2 = DiagnosisSession(
        session_id="test-2",
        line_name="LineB",
        included_tools=["ToolA", "ToolB"],
    )
    assert session2.included_tools == ["ToolA", "ToolB"]


def test_session_has_report_overrides():
    """Session should have report_overrides field defaulting to empty dict."""
    session = DiagnosisSession(session_id="test-1", line_name="LineA")
    assert hasattr(session, "report_overrides")
    assert session.report_overrides == {}

    session2 = DiagnosisSession(
        session_id="test-2",
        line_name="LineB",
        report_overrides={"chapter_order": ["intro", "details"]},
    )
    assert session2.report_overrides == {"chapter_order": ["intro", "details"]}


def test_session_has_tool_order():
    """Session should have tool_order field defaulting to None."""
    session = DiagnosisSession(session_id="test-1", line_name="LineA")
    assert hasattr(session, "tool_order")
    assert session.tool_order is None

    session2 = DiagnosisSession(
        session_id="test-2",
        line_name="LineB",
        tool_order=["ToolA", "ToolB", "ToolC"],
    )
    assert session2.tool_order == ["ToolA", "ToolB", "ToolC"]


def test_session_has_active_skill_name():
    """Session should have active_skill_name field defaulting to None."""
    session = DiagnosisSession(session_id="test-1", line_name="LineA")
    assert hasattr(session, "active_skill_name")
    assert session.active_skill_name is None

    session2 = DiagnosisSession(
        session_id="test-2",
        line_name="LineB",
        active_skill_name="advanced_diagnosis",
    )
    assert session2.active_skill_name == "advanced_diagnosis"
