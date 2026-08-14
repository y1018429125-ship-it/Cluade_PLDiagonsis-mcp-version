"""Tests for the weather diagnosis HTTP service."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from engine import _parse_date, build_report, classify_humidity
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
    assert data["tool_name"] == "WeatherDiagnosisTool"


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


def test_classify_humidity_very_humid():
    assert classify_humidity(80.161) == "空气极为潮湿，有利于雷暴形成条件"
    assert classify_humidity(70.001) == "空气极为潮湿，有利于雷暴形成条件"


def test_classify_humidity_moderately_humid():
    assert classify_humidity(70.0) == "空气较为潮湿，符合雷暴形成条件"
    assert classify_humidity(40.0) == "空气较为潮湿，符合雷暴形成条件"


def test_classify_humidity_dry():
    assert classify_humidity(39.9) == "空气干燥，不符合雷暴形成条件"
    assert classify_humidity(0.0) == "空气干燥，不符合雷暴形成条件"


def _weather(code: int | str, tmp: float | None = None, hum: float | None = None) -> WeatherResponse:
    if tmp is None or hum is None:
        return WeatherResponse(code=code, data=None)
    return WeatherResponse(
        code=code,
        data=WeatherData(real=WeatherReal(tmp=tmp, hum=hum)),
    )


def test_build_report_normal():
    report = build_report(_weather(1001, tmp=26.5, hum=80.161))
    assert report["error"] is None
    assert report["temperature_c"] == 26.5
    assert report["humidity_pct"] == 80.161
    assert report["humidity_description"] == "空气极为潮湿，有利于雷暴形成条件"
    assert "温度：26.500 °C" in report["markdown"]
    assert "湿度：80.161%" in report["markdown"]
    assert "该区域故障时刻湿度为 **80.161%**，空气极为潮湿，有利于雷暴形成条件。" in report["markdown"]
    # No confidence/weight section must exist.
    assert "置信度" not in report["markdown"]
    assert "权重" not in report["markdown"]


def test_build_report_api_error_code():
    report = build_report(_weather(5000, tmp=26.5, hum=80.0))
    assert report["error"] == "getWeather 接口数据同步异常"
    assert report["temperature_c"] is None
    assert "数据同步异常" in report["markdown"]


def test_build_report_missing_data():
    report = build_report(_weather(1001))
    assert report["error"] == "getWeather 接口数据同步异常"
    assert report["humidity_pct"] is None
    assert report["humidity_description"] == "数据异常"
