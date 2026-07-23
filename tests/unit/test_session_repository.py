"""Tests for SessionRepository JSON persistence."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.core.models import (
    DiagnosisSession,
    DiagnosisSummary,
    DiagnosisResult,
    SessionStatus,
    ConfidenceLevel,
    FaultContext,
)
from src.infrastructure.session_repository import SessionRepository


class TestSessionRepository:
    @pytest.fixture
    def temp_repo(self, tmp_path):
        file_path = tmp_path / "test_sessions.json"
        return SessionRepository(file_path)

    def test_load_empty_when_file_missing(self, tmp_path):
        repo = SessionRepository(tmp_path / "nonexistent.json")
        sessions = repo.load_all()
        assert sessions == {}

    def test_save_and_load_single_session(self, temp_repo):
        session = DiagnosisSession(
            session_id="sess_001",
            line_name="京西线",
            status=SessionStatus.COMPLETED,
        )
        temp_repo.save_all({"sess_001": session})

        loaded = temp_repo.load_all()
        assert len(loaded) == 1
        assert loaded["sess_001"].session_id == "sess_001"
        assert loaded["sess_001"].line_name == "京西线"
        assert loaded["sess_001"].status == SessionStatus.COMPLETED

    def test_save_and_load_with_summary(self, temp_repo):
        summary = DiagnosisSummary(
            version=1,
            results=[
                DiagnosisResult(
                    fault_type="雷电",
                    confidence=0.85,
                    confidence_level=ConfidenceLevel.HIGH,
                    tool_name="LightningDiagnosisTool",
                )
            ],
        )
        session = DiagnosisSession(
            session_id="sess_002",
            line_name="武昌线",
            status=SessionStatus.MODIFYING,
            summaries=[summary],
        )
        temp_repo.save_all({"sess_002": session})

        loaded = temp_repo.load_all()
        assert len(loaded) == 1
        loaded_session = loaded["sess_002"]
        assert loaded_session.line_name == "武昌线"
        assert len(loaded_session.summaries) == 1
        assert loaded_session.summaries[0].version == 1
        assert len(loaded_session.summaries[0].results) == 1
        assert loaded_session.summaries[0].results[0].fault_type == "雷电"
        assert loaded_session.summaries[0].results[0].confidence == 0.85

    def test_save_atomic_write(self, temp_repo):
        """保存应使用临时文件 + 替换，避免写入中断导致文件损坏。"""
        session = DiagnosisSession(
            session_id="sess_003",
            line_name="宁东线",
        )
        temp_repo.save_all({"sess_003": session})

        # 确保没有残留的临时文件
        temp_file = temp_repo._file.with_suffix(".tmp")
        assert not temp_file.exists()

        # 确保正式文件存在且格式正确
        assert temp_repo._file.exists()
        with open(temp_repo._file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == 1
        assert len(data["sessions"]) == 1

    def test_load_corrupted_json_returns_empty(self, temp_repo):
        temp_repo._file.write_text("not valid json", encoding="utf-8")
        loaded = temp_repo.load_all()
        assert loaded == {}

    def test_load_invalid_session_skips_gracefully(self, temp_repo):
        data = {
            "version": 1,
            "sessions": [
                {"session_id": "valid", "line_name": "ok", "status": "pending"},
                {"invalid": "missing required fields"},
            ],
        }
        with open(temp_repo._file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = temp_repo.load_all()
        assert len(loaded) == 1
        assert "valid" in loaded

    def test_delete_file(self, temp_repo):
        session = DiagnosisSession(session_id="sess_del", line_name="test")
        temp_repo.save_all({"sess_del": session})
        assert temp_repo._file.exists()

        temp_repo.delete_file()
        assert not temp_repo._file.exists()

    def test_roundtrip_datetime_fields(self, temp_repo):
        session = DiagnosisSession(
            session_id="sess_dt",
            line_name="test",
            created_at=datetime(2025, 5, 11, 10, 30, 0),
            updated_at=datetime(2025, 5, 11, 11, 0, 0),
        )
        temp_repo.save_all({"sess_dt": session})

        loaded = temp_repo.load_all()
        loaded_session = loaded["sess_dt"]
        assert loaded_session.created_at == datetime(2025, 5, 11, 10, 30, 0)
        assert loaded_session.updated_at == datetime(2025, 5, 11, 11, 0, 0)

    def test_roundtrip_fault_context(self, temp_repo):
        fc = FaultContext(
            line_id="L001",
            line_name="京西线",
            tower_id="T-102",
        )
        summary = DiagnosisSummary(
            version=1,
            fault_context=fc,
        )
        session = DiagnosisSession(
            session_id="sess_fc",
            line_name="京西线",
            summaries=[summary],
        )
        temp_repo.save_all({"sess_fc": session})

        loaded = temp_repo.load_all()
        loaded_summary = loaded["sess_fc"].summaries[0]
        assert loaded_summary.fault_context is not None
        assert loaded_summary.fault_context.line_id == "L001"
        assert loaded_summary.fault_context.tower_id == "T-102"
