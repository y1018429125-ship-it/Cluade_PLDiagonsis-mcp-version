"""Tests for web.py REST API endpoints."""

import pytest

from src.interfaces.web import create_app


class TestListTools:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_list_tools_returns_array(self, client):
        """GET /api/tools returns a list of tool objects."""
        resp = client.get("/api/tools")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tools" in data
        assert isinstance(data["tools"], list)


class TestGetSession:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_get_session_404_for_unknown(self, client):
        """GET /api/sessions/<id> returns 404 for unknown session."""
        resp = client.get("/api/sessions/sess_nonexistent")
        assert resp.status_code == 404
