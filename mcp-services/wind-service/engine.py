"""Wind-speed description engine for the wind diagnosis service.

This tool outputs only the fault-time wind speed and a description
sentence. The wind-speed threshold (10 m/s) only selects which description
sentence to output — it is NOT a confidence score and carries no weight
in the PLD weighted diagnosis.
"""

from __future__ import annotations

import re

from config import DECIMAL_PLACES
from engine_models import WeatherResponse

# Wind speed threshold in m/s (60% of design wind speed).
WIND_SPEED_THRESHOLD: float = 10.0


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


def classify_wind_speed(ws: float) -> str:
    """Return the wind-speed description sentence.

    The threshold only selects the description text; it does not represent
    any confidence or weight.

    Args:
        ws: Wind speed in m/s.

    Returns:
        Description sentence for the wind-speed level.
    """
    if ws <= WIND_SPEED_THRESHOLD:
        return "风速小于设计风速的60%，无风偏故障风险"
    return "风速大于设计风速的60%，请关注是否存在风偏故障"


def build_report(weather: WeatherResponse) -> dict:
    """Build the wind Markdown report from getWeather data.

    Args:
        weather: Parsed getWeather response.

    Returns:
        Dict with keys: markdown, wind_speed_ms, wind_description, error.
    """
    if (
        str(weather.code) != "1001"
        or weather.data is None
        or weather.data.real is None
    ):
        return {
            "markdown": "## 风偏诊断\n\ngetWeather 接口数据同步异常，无法获取故障时刻风速信息。\n",
            "wind_speed_ms": None,
            "wind_description": "数据异常",
            "error": "getWeather 接口数据同步异常",
        }

    ws = weather.data.real.ws
    description = classify_wind_speed(ws)

    markdown = f"""## 风偏诊断

### 故障时刻风速信息

- 风速：{_format(ws)} m/s

### 风偏分析

该区域故障时刻风速为 **{_format(ws)} m/s**，{description}。
"""

    return {
        "markdown": markdown,
        "wind_speed_ms": ws,
        "wind_description": description,
        "error": None,
    }
