"""Humidity-level description engine for the weather diagnosis service.

This tool outputs only temperature, humidity, and a humidity-level
description sentence. The humidity levels (>70 / >=40 / else) only select
which description sentence to output — they are NOT confidence scores and
carry no weight in the PLD weighted diagnosis.
"""

from __future__ import annotations

import re

from config import DECIMAL_PLACES
from engine_models import WeatherResponse


def _format(value: float) -> str:
    """Format a float to the configured number of decimal places."""
    return f"{value:.{DECIMAL_PLACES}f}"


def _parse_date(query_date: str) -> str:
    """Parse Chinese or ISO date into YYYY-MM-DD.

    Args:
        query_date: Date string like "2025-05-08" or "2025年5月8日".

    Returns:
        ISO format date string.

    Raises:
        ValueError: If the date format is not recognized.
    """
    query_date = query_date.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", query_date):
        return query_date
    match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", query_date)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    raise ValueError(f"无法识别的日期格式: {query_date}")


def classify_humidity(hum: float) -> str:
    """Return the humidity-level description sentence.

    Reuses the exact wording of the removed lightning-diagnosis module 4
    (micro-weather). The thresholds only select the description text; they
    do not represent any confidence or weight.

    Args:
        hum: Relative humidity in percent.

    Returns:
        Description sentence for the humidity level.
    """
    if hum > 70.0:
        return "空气极为潮湿，有利于雷暴形成条件"
    if hum >= 40.0:
        return "空气较为潮湿，符合雷暴形成条件"
    return "空气干燥，不符合雷暴形成条件"


def build_report(weather: WeatherResponse) -> dict:
    """Build the weather Markdown report from getWeather data.

    Args:
        weather: Parsed getWeather response.

    Returns:
        Dict with keys: markdown, temperature_c, humidity_pct,
        humidity_description, error.
    """
    if (
        str(weather.code) != "1001"
        or weather.data is None
        or weather.data.real is None
    ):
        return {
            "markdown": "## 气象诊断\n\ngetWeather 接口数据同步异常，无法获取故障时刻气象信息。\n",
            "temperature_c": None,
            "humidity_pct": None,
            "humidity_description": "数据异常",
            "error": "getWeather 接口数据同步异常",
        }

    real = weather.data.real
    tmp = real.tmp
    hum = real.hum
    description = classify_humidity(hum)

    markdown = f"""## 气象诊断

### 故障时刻气象信息

- 温度：{_format(tmp)} °C
- 湿度：{_format(hum)}%

### 气象分析

该区域故障时刻湿度为 **{_format(hum)}%**，{description}。
"""

    return {
        "markdown": markdown,
        "temperature_c": tmp,
        "humidity_pct": hum,
        "humidity_description": description,
        "error": None,
    }
