"""Tests for web.py static file serving."""

import os
from pathlib import Path

import pytest

from src.interfaces.web import create_app


class TestStaticFileServing:
    def test_serves_index_html_at_root(self, tmp_path: Path) -> None:
        """When dist/index.html exists, root path returns it."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")

        old_env = os.environ.get("FRONTEND_DIST")
        os.environ["FRONTEND_DIST"] = str(dist)
        try:
            app = create_app()
            with app.test_client() as client:
                resp = client.get("/")
                assert resp.status_code == 200
                assert b"<html>app</html>" in resp.data
        finally:
            if old_env is None:
                os.environ.pop("FRONTEND_DIST", None)
            else:
                os.environ["FRONTEND_DIST"] = old_env

    def test_serves_static_asset(self, tmp_path: Path) -> None:
        """Existing files under dist are served directly."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
        assets = dist / "assets"
        assets.mkdir()
        (assets / "main.js").write_text("console.log(1)", encoding="utf-8")

        old_env = os.environ.get("FRONTEND_DIST")
        os.environ["FRONTEND_DIST"] = str(dist)
        try:
            app = create_app()
            with app.test_client() as client:
                resp = client.get("/assets/main.js")
                assert resp.status_code == 200
                assert b"console.log(1)" in resp.data
        finally:
            if old_env is None:
                os.environ.pop("FRONTEND_DIST", None)
            else:
                os.environ["FRONTEND_DIST"] = old_env

    def test_fallback_to_index_for_unknown_paths(self, tmp_path: Path) -> None:
        """Non-file paths fall back to index.html (SPA routing)."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")

        old_env = os.environ.get("FRONTEND_DIST")
        os.environ["FRONTEND_DIST"] = str(dist)
        try:
            app = create_app()
            with app.test_client() as client:
                resp = client.get("/some-vue-route")
                assert resp.status_code == 200
                assert b"<html>spa</html>" in resp.data
        finally:
            if old_env is None:
                os.environ.pop("FRONTEND_DIST", None)
            else:
                os.environ["FRONTEND_DIST"] = old_env

    def test_no_static_routes_when_dist_missing(self, tmp_path: Path) -> None:
        """When dist directory does not exist, no static routes are registered."""
        old_env = os.environ.get("FRONTEND_DIST")
        os.environ["FRONTEND_DIST"] = str(tmp_path / "nonexistent")
        try:
            app = create_app()
            with app.test_client() as client:
                # API routes still work
                resp = client.get("/api/health")
                assert resp.status_code == 200
        finally:
            if old_env is None:
                os.environ.pop("FRONTEND_DIST", None)
            else:
                os.environ["FRONTEND_DIST"] = old_env
