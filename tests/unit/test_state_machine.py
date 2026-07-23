"""Tests for src/domain/state_machine.py — state transitions and permissions."""

import pytest

from src.core.exceptions import InvalidStateError
from src.core.models import DiagnosisSession, EventType, SessionStatus
from src.domain.state_machine import VALID_TRANSITIONS, StateMachine
from src.infrastructure.event_bus import EventBus


# ============================================================================
# can_transition — valid paths
# ============================================================================


def test_pending_can_transition_to_diagnosing(state_machine: StateMachine) -> None:
    """PENDING -> DIAGNOSING is the only valid first step."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    assert state_machine.can_transition(session, SessionStatus.DIAGNOSING) is True


def test_diagnosing_can_transition_to_modifying(state_machine: StateMachine) -> None:
    """DIAGNOSING -> MODIFYING is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.DIAGNOSING)
    assert state_machine.can_transition(session, SessionStatus.MODIFYING) is True


def test_diagnosing_can_transition_to_excluded(state_machine: StateMachine) -> None:
    """DIAGNOSING -> EXCLUDED is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.DIAGNOSING)
    assert state_machine.can_transition(session, SessionStatus.EXCLUDED) is True


def test_diagnosing_can_transition_to_rechecking(state_machine: StateMachine) -> None:
    """DIAGNOSING -> RECHECKING is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.DIAGNOSING)
    assert state_machine.can_transition(session, SessionStatus.RECHECKING) is True


def test_modifying_can_transition_to_completed(state_machine: StateMachine) -> None:
    """MODIFYING -> COMPLETED is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.MODIFYING)
    assert state_machine.can_transition(session, SessionStatus.COMPLETED) is True


def test_modifying_can_self_transition(state_machine: StateMachine) -> None:
    """MODIFYING -> MODIFYING is allowed."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.MODIFYING)
    assert state_machine.can_transition(session, SessionStatus.MODIFYING) is True


def test_completed_can_transition_to_rechecking(state_machine: StateMachine) -> None:
    """COMPLETED -> RECHECKING is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.COMPLETED)
    assert state_machine.can_transition(session, SessionStatus.RECHECKING) is True


def test_completed_can_transition_to_modifying(state_machine: StateMachine) -> None:
    """COMPLETED -> MODIFYING is valid."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.COMPLETED)
    assert state_machine.can_transition(session, SessionStatus.MODIFYING) is True


# ============================================================================
# can_transition — invalid paths
# ============================================================================


def test_pending_cannot_transition_to_modifying(state_machine: StateMachine) -> None:
    """PENDING -> MODIFYING is illegal."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    assert state_machine.can_transition(session, SessionStatus.MODIFYING) is False


def test_pending_cannot_transition_to_completed(state_machine: StateMachine) -> None:
    """PENDING -> COMPLETED is illegal."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    assert state_machine.can_transition(session, SessionStatus.COMPLETED) is False


def test_pending_cannot_transition_to_excluded(state_machine: StateMachine) -> None:
    """PENDING -> EXCLUDED is illegal."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    assert state_machine.can_transition(session, SessionStatus.EXCLUDED) is False


def test_completed_cannot_transition_to_diagnosing(state_machine: StateMachine) -> None:
    """COMPLETED -> DIAGNOSING is illegal."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.COMPLETED)
    assert state_machine.can_transition(session, SessionStatus.DIAGNOSING) is False


def test_excluded_cannot_transition_to_diagnosing(state_machine: StateMachine) -> None:
    """EXCLUDED -> DIAGNOSING is illegal."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.EXCLUDED)
    assert state_machine.can_transition(session, SessionStatus.DIAGNOSING) is False


# ============================================================================
# transition — execution
# ============================================================================


@pytest.mark.asyncio
async def test_transition_updates_session_status(state_machine: StateMachine) -> None:
    """transition() mutates session.status to the target value."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    state_machine.transition(session, SessionStatus.DIAGNOSING)
    assert session.status == SessionStatus.DIAGNOSING


@pytest.mark.asyncio
async def test_transition_updates_timestamp(state_machine: StateMachine) -> None:
    """transition() refreshes session.updated_at."""
    from datetime import datetime, timedelta

    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    old_time = session.updated_at
    state_machine.transition(session, SessionStatus.DIAGNOSING)
    assert session.updated_at > old_time


@pytest.mark.asyncio
async def test_transition_raises_on_illegal_move(state_machine: StateMachine) -> None:
    """transition() raises InvalidStateError for illegal transitions."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    with pytest.raises(InvalidStateError) as exc_info:
        state_machine.transition(session, SessionStatus.MODIFYING)
    assert "pending" in str(exc_info.value).lower()
    assert "modifying" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_transition_publishes_status_event_via_event_bus(event_bus: EventBus) -> None:
    """transition() publishes a STATUS event through the event bus."""
    received: list = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe_session("s1", handler)

    sm = StateMachine(event_bus)
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    sm.transition(session, SessionStatus.DIAGNOSING)

    import asyncio
    await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].event_type == EventType.STATUS
    assert received[0].payload["status"] == "diagnosing"
    assert received[0].payload["previous"] == "pending"


# ============================================================================
# can_execute — command permissions
# ============================================================================


def test_pending_allows_diagnose_only(state_machine: StateMachine) -> None:
    """PENDING permits only the 'diagnose' command."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.PENDING)
    assert state_machine.can_execute(session, "diagnose") is True
    assert state_machine.can_execute(session, "exclude") is False
    assert state_machine.can_execute(session, "modify") is False


def test_diagnosing_allows_exclude_and_recheck(state_machine: StateMachine) -> None:
    """DIAGNOSING permits 'exclude' and 'recheck'."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.DIAGNOSING)
    assert state_machine.can_execute(session, "exclude") is True
    assert state_machine.can_execute(session, "recheck") is True
    assert state_machine.can_execute(session, "modify") is False


def test_modifying_allows_broad_commands(state_machine: StateMachine) -> None:
    """MODIFYING permits modify, exclude, recheck, adjust_weight, complete, save_strategy, diagnose."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.MODIFYING)
    for cmd in ("modify", "exclude", "recheck", "adjust_weight", "complete", "save_strategy", "diagnose"):
        assert state_machine.can_execute(session, cmd) is True


def test_completed_allows_recheck_modify_save_strategy(state_machine: StateMachine) -> None:
    """COMPLETED permits recheck, modify, save_strategy."""
    session = DiagnosisSession(session_id="s1", line_name="L", status=SessionStatus.COMPLETED)
    assert state_machine.can_execute(session, "recheck") is True
    assert state_machine.can_execute(session, "modify") is True
    assert state_machine.can_execute(session, "save_strategy") is True
    assert state_machine.can_execute(session, "diagnose") is False


def test_unknown_command_always_denied(state_machine: StateMachine) -> None:
    """Arbitrary unknown commands are denied in every state."""
    for status in SessionStatus:
        session = DiagnosisSession(session_id="s1", line_name="L", status=status)
        assert state_machine.can_execute(session, "unknown_command") is False


# ============================================================================
# VALID_TRANSITIONS table integrity
# ============================================================================


def test_valid_transitions_has_entry_for_every_status() -> None:
    """Every SessionStatus appears as a key in VALID_TRANSITIONS."""
    for status in SessionStatus:
        assert status in VALID_TRANSITIONS
