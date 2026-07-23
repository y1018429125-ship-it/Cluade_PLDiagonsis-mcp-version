"""Tests for settings and session clear REST API endpoints."""

import pytest

from src.interfaces.web import create_app


class TestGetSettings:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_get_settings_returns_defaults(self, client):
        """GET /api/settings returns system settings."""
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "default_weights" in data
        assert "weight_range" in data
        assert "llm" in data
        assert "min" in data["weight_range"]
        assert "max" in data["weight_range"]
        assert "provider" in data["llm"]
        assert "model" in data["llm"]


class TestClearSessions:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_clear_sessions_returns_success(self, client):
        """POST /api/sessions/clear returns success."""
        resp = client.post("/api/sessions/clear")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "message" in data


class TestUpdateWeights:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_update_weights_no_active_session(self, client):
        """POST /api/settings/weights returns 400 without active session."""
        resp = client.post(
            "/api/settings/weights", json={"weights": {"LightningDiagnosisTool": 1.5}}
        )
        assert resp.status_code == 400
        assert "没有活跃的会话" in resp.get_json()["error"]

    def test_update_weights_missing_weights(self, client):
        """POST /api/settings/weights returns 400 without weights."""
        resp = client.post("/api/settings/weights", json={})
        assert resp.status_code == 400
        assert "weights 不能为空" in resp.get_json()["error"]
