"""Tests for the wind diagnosis HTTP service."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from engine import _parse_date, build_report, classify_wind_speed
from engine_models import WeatherData, WeatherReal, WeatherResponse
from main import app, _extract_query_date


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tool_name"] == "WindDiagnosisTool"


def test_extract_query_date_from_datetime():
    dt = datetime(2025, 5, 8, 19, 46, 30)
    assert _extract_query_date(dt, {}) == "2025-05-08"


def test_extract_query_date_from_additional_info():
    assert _extract_query_date(None, {"query_date": "2025年5月8日"}) == "2025-05-08"


def test_extract_query_date_missing():
    with pytest.raises(ValueError):
        _extract_query_date(None, {})


def test_parse_date_chinese_format():
    assert _parse_date("2025年5月8日") == "2025-05-08"
    assert _parse_date("2025-05-08") == "2025-05-08"


def test_classify_wind_speed_no_risk():
    assert classify_wind_speed(3.40831) == "风速小于设计风速的60%，无风偏故障风险"
    assert classify_wind_speed(10.0) == "风速小于设计风速的60%，无风偏故障风险"
    assert classify_wind_speed(0.0) == "风速小于设计风速的60%，无风偏故障风险"


def test_classify_wind_speed_risk():
    assert classify_wind_speed(10.001) == "风速大于设计风速的60%，请关注是否存在风偏故障"
    assert classify_wind_speed(25.0) == "风速大于设计风速的60%，请关注是否存在风偏故障"


def _weather(code: int | str, ws: float | None = None) -> WeatherResponse:
    if ws is None:
        return WeatherResponse(code=code, data=None)
    return WeatherResponse(
        code=code,
        data=WeatherData(real=WeatherReal(ws=ws)),
    )


def test_build_report_normal():
    report = build_report(_weather(1001, ws=3.40831))
    assert report["error"] is None
    assert report["wind_speed_ms"] == 3.40831
    assert report["wind_description"] == "风速小于设计风速的60%，无风偏故障风险"
    assert "风速：3.408 m/s" in report["markdown"]
    assert "该区域故障时刻风速为 **3.408 m/s**，风速小于设计风速的60%，无风偏故障风险。" in report["markdown"]
    # No confidence/weight section must exist.
    assert "置信度" not in report["markdown"]
    assert "权重" not in report["markdown"]


def test_build_report_high_wind():
    report = build_report(_weather(1001, ws=18.5))
    assert report["wind_description"] == "风速大于设计风速的60%，请关注是否存在风偏故障"
    assert "请关注是否存在风偏故障" in report["markdown"]


def test_build_report_api_error_code():
    report = build_report(_weather(5000, ws=3.4))
    assert report["error"] == "getWeather 接口数据同步异常"
    assert report["wind_speed_ms"] is None
    assert "数据同步异常" in report["markdown"]


def test_build_report_missing_data():
    report = build_report(_weather(1001))
    assert report["error"] == "getWeather 接口数据同步异常"
    assert report["wind_speed_ms"] is None
    assert report["wind_description"] == "数据异常"
