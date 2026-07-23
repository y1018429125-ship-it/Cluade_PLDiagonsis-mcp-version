"""Tests for skills REST API endpoints."""

import json
from pathlib import Path

import pytest

from src.interfaces.web import create_app


class TestListSkills:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_list_skills_empty(self, client, tmp_path):
        """GET /api/skills returns empty list when no skills exist."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        from src.interfaces.dependency_injection import get_container

        container = get_container()
        original_dir = container.skill_loader._skills_dir
        container.skill_loader._skills_dir = skills_dir
        container.skill_loader._cache.clear()
        try:
            resp = client.get("/api/skills")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "skills" in data
            assert data["skills"] == []
        finally:
            container.skill_loader._skills_dir = original_dir
            container.skill_loader._cache.clear()

    def test_list_skills_returns_saved(self, client, tmp_path):
        """GET /api/skills returns skills from skills/ directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "my_skill.md"
        skill_file.write_text(
            "# Test Skill\n\n## 描述\n\nA test skill for diagnosis.\n",
            encoding="utf-8",
        )

        from src.interfaces.dependency_injection import get_container

        container = get_container()
        original_dir = container.skill_loader._skills_dir
        container.skill_loader._skills_dir = skills_dir
        container.skill_loader._cache.clear()
        try:
            resp = client.get("/api/skills")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["skills"]) == 1
            assert data["skills"][0]["name"] == "my_skill"
            assert data["skills"][0]["description"] == "Test Skill"
        finally:
            container.skill_loader._skills_dir = original_dir
            container.skill_loader._cache.clear()


class TestDeleteSkill:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_delete_missing_strategy(self, client):
        """DELETE /api/skills/<name> returns 404 for missing strategy."""
        resp = client.delete("/api/skills/nonexistent")
        assert resp.status_code == 404
        assert "不存在" in resp.get_json()["error"]


class TestResetSkills:
    @pytest.fixture
    def client(self):
        app = create_app()
        with app.test_client() as client:
            yield client

    def test_reset_no_active_session(self, client):
        """POST /api/skills/reset returns 400 without active session."""
        resp = client.post("/api/skills/reset")
        assert resp.status_code == 400
        assert "没有活跃的会话" in resp.get_json()["error"]
