"""Tests for the lightning diagnosis HTTP service."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from main import app, _extract_query_date, _extract_fault_type_and_confidence


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tool_name"] == "LightningDiagnosisTool"


def test_extract_query_date_from_datetime():
    dt = datetime(2025, 5, 8, 19, 46, 30)
    assert _extract_query_date(dt, {}) == "2025-05-08"


def test_extract_query_date_from_additional_info():
    assert _extract_query_date(None, {"query_date": "2025年5月8日"}) == "2025-05-08"


def test_extract_query_date_missing():
    with pytest.raises(ValueError):
        _extract_query_date(None, {})


def test_extract_fault_type_and_confidence():
    markdown = "最终诊断结论为：**雷击-绕击**，综合置信度为0.985"
    fault_type, confidence = _extract_fault_type_and_confidence(markdown)
    assert fault_type == "雷击-绕击"
    assert confidence == 0.985


def test_extract_fault_type_fallback():
    markdown = "基于故障波形分析，输电线路故障类型为雷击-反击。"
    fault_type, confidence = _extract_fault_type_and_confidence(markdown)
    assert fault_type == "雷击-反击"
    assert confidence == 0.0
