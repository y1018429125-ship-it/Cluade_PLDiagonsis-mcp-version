"""Tests for src/infrastructure/fault_parser.py"""

from datetime import datetime

import pytest

from src.infrastructure.fault_parser import FaultContextParser


class TestExtractLineName:
    def test_extracts_voltage_and_name(self):
        line, voltage = FaultContextParser._extract_line_name("220kV京西线发生故障")
        assert line == "京西线"
        assert voltage == "220kV"

    def test_extracts_name_without_voltage(self):
        line, voltage = FaultContextParser._extract_line_name("京西线跳闸了")
        assert line == "京西线"
        assert voltage == ""

    def test_fallback_when_no_match(self):
        line, voltage = FaultContextParser._extract_line_name("没有线路名称", "默认线")
        assert line == "默认线"
        assert voltage == ""


class TestExtractTowerId:
    def test_extracts_tower_with_hash(self):
        assert FaultContextParser._extract_tower_id("#102塔故障") == "T-102"

    def test_extracts_tower_with_chinese(self):
        assert FaultContextParser._extract_tower_id("第205号塔") == "T-205"

    def test_returns_none_when_no_tower(self):
        assert FaultContextParser._extract_tower_id("没有杆塔信息") is None


class TestExtractFaultTime:
    def test_extracts_iso_datetime(self):
        dt = FaultContextParser._extract_fault_time("故障时间：2024-06-15 14:30:00")
        assert dt == datetime(2024, 6, 15, 14, 30, 0)

    def test_extracts_chinese_datetime(self):
        dt = FaultContextParser._extract_fault_time("2024年6月15日14时30分发生故障")
        assert dt == datetime(2024, 6, 15, 14, 30, 0)

    def test_extracts_short_datetime(self):
        dt = FaultContextParser._extract_fault_time("6月15日14:30跳闸")
        now = datetime.now()
        assert dt == datetime(now.year, 6, 15, 14, 30, 0)

    def test_extracts_today(self):
        dt = FaultContextParser._extract_fault_time("今天发生故障")
        now = datetime.now()
        expected = now.replace(hour=12, minute=0, second=0, microsecond=0)
        assert dt == expected

    def test_returns_none_when_no_time(self):
        assert FaultContextParser._extract_fault_time("没有时间的消息") is None

    def test_parse_time_with_milliseconds(self):
        dt = FaultContextParser._extract_fault_time("2026-05-12 08:00:05.013")
        assert dt == datetime(2026, 5, 12, 8, 0, 5, 13000)

    def test_parse_time_without_milliseconds(self):
        dt = FaultContextParser._extract_fault_time("2026-05-12 08:00:05")
        assert dt == datetime(2026, 5, 12, 8, 0, 5, 0)

    def test_parse_time_minute_only(self):
        dt = FaultContextParser._extract_fault_time("2026-05-12 08:00")
        assert dt == datetime(2026, 5, 12, 8, 0, 0, 0)


class TestExtractWeather:
    def test_extracts_condition(self):
        weather = FaultContextParser._extract_weather("当时天气雷阵雨，气温25度")
        assert weather is not None
        assert "雷阵雨" in weather["condition"]

    def test_extracts_temperature(self):
        weather = FaultContextParser._extract_weather("气温：-2.5°C")
        assert weather is not None
        assert weather["temperature"] == -2.5

    def test_extracts_wind_speed(self):
        weather = FaultContextParser._extract_weather("风速：8.5m/s")
        assert weather is not None
        assert weather["wind_speed"] == 8.5

    def test_extracts_humidity(self):
        weather = FaultContextParser._extract_weather("湿度：85%")
        assert weather is not None
        assert weather["humidity"] == 85.0

    def test_returns_none_when_no_weather(self):
        assert FaultContextParser._extract_weather("没有天气信息") is None


class TestDetectFaultTypes:
    def test_detects_lightning(self):
        types = FaultContextParser._detect_fault_types("疑似雷击故障")
        assert "lightning" in types

    def test_detects_icing(self):
        types = FaultContextParser._detect_fault_types("覆冰严重导致跳闸")
        assert "icing" in types

    def test_detects_wind(self):
        types = FaultContextParser._detect_fault_types("大风引起风偏")
        assert "wind" in types

    def test_detects_bird(self):
        types = FaultContextParser._detect_fault_types("鸟害导致短路")
        assert "bird" in types

    def test_detects_multiple(self):
        types = FaultContextParser._detect_fault_types("雷击后覆冰加重")
        assert "lightning" in types
        assert "icing" in types

    def test_returns_empty_when_no_match(self):
        types = FaultContextParser._detect_fault_types("正常运行")
        assert types == []


class TestExtractScadaData:
    def test_extracts_current(self):
        data = FaultContextParser._extract_scada_data("电流：120A")
        assert data is not None
        assert data["current"] == 120.0

    def test_extracts_voltage(self):
        data = FaultContextParser._extract_scada_data("电压220kV")
        assert data is not None
        assert data["voltage"] == 220.0

    def test_extracts_power(self):
        data = FaultContextParser._extract_scada_data("功率：50MW")
        assert data is not None
        assert data["power"] == 50.0

    def test_returns_none_when_no_scada(self):
        assert FaultContextParser._extract_scada_data("无数据") is None


class TestParseFull:
    def test_parses_complex_message(self):
        msg = "220kV京西线#102塔，2024-06-15 14:30:00发生雷击故障，当时雷阵雨，气温28度"
        ctx = FaultContextParser.parse(msg)

        assert ctx.line_name == "京西线"
        assert ctx.tower_id == "T-102"
        assert ctx.fault_time == datetime(2024, 6, 15, 14, 30, 0)
        assert ctx.weather_info is not None
        assert "雷阵雨" in ctx.weather_info["condition"]
        assert ctx.additional_info["voltage_level"] == "220kV"
        assert "lightning" in ctx.additional_info["detected_fault_types"]

    def test_uses_fallback_line_name(self):
        ctx = FaultContextParser.parse("发生故障了", session_line_name="京西线")
        assert ctx.line_name == "京西线"

    def test_preserves_user_input(self):
        msg = "简单的故障描述"
        ctx = FaultContextParser.parse(msg)
        assert ctx.additional_info["user_input"] == msg
