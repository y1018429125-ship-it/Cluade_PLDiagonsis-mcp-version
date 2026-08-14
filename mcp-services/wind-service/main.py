"""FastAPI service entry for the wind fault diagnosis tool.

This service exposes the same HTTP interface as the other PLDiagnosis
MCP services. It consumes the getWeather API (wind speed only) and outputs
a pure language description — no confidence or weight is produced for the
PLD weighted diagnosis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from client import APIClient, APIClientError, DataNotFoundError
from engine import _parse_date, build_report
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Wind Diagnosis MCP Service")


def _extract_query_date(fault_time: datetime | None, additional_info: dict[str, Any]) -> str:
    """Extract query_date from fault_time or additional_info.

    Args:
        fault_time: Parsed fault datetime.
        additional_info: Extra context that may contain a date.

    Returns:
        Date string in YYYY-MM-DD format.

    Raises:
        ValueError: If no usable date is found.
    """
    if fault_time is not None:
        return fault_time.strftime("%Y-%m-%d")

    raw = additional_info.get("query_date") if isinstance(additional_info, dict) else None
    if isinstance(raw, str):
        return _parse_date(raw)

    raise ValueError("缺少故障日期（fault_time 或 additional_info.query_date）")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WindDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    """Fetch fault-time wind speed and describe the wind-deflection risk."""
    client = APIClient()
    try:
        query_date = _extract_query_date(req.fault_time, req.additional_info or {})
        trip_id = await client.get_trip_info_data(query_date, req.line_name)
        weather = await client.get_weather(trip_id)
        report = build_report(weather)

        structured_data: dict[str, Any] = {
            "wind_speed_ms": report["wind_speed_ms"],
            "wind_description": report["wind_description"],
            "details": {
                "query_date": query_date,
                "trip_id": trip_id,
            },
        }
        if report["error"]:
            structured_data["error"] = report["error"]

        return DiagnoseResponse(
            tool_name="WindDiagnosisTool",
            raw_text=report["markdown"],
            structured_data=structured_data,
            metadata={
                "source": "特高压气象数据",
                "data_quality": "real",
                "query_date": query_date,
            },
            timestamp=datetime.now(timezone.utc),
        )
    except DataNotFoundError as exc:
        logger.error(f"未找到记录: {exc.message}")
        raise HTTPException(status_code=404, detail=exc.message)
    except APIClientError as exc:
        logger.error(f"风速查询失败: {exc.message}")
        raise HTTPException(status_code=500, detail=exc.message)
    except Exception as exc:
        logger.error(f"未知错误: {exc}")
        raise HTTPException(status_code=500, detail=f"风速查询过程中发生未知错误: {exc}")
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
