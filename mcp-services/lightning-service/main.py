"""FastAPI service entry for the lightning fault diagnosis tool.

This service exposes the same HTTP interface as the other PLDiagnosis
MCP services so it can be dropped into mcp-services/lightning-service.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from client import APIClient, APIClientError, DataNotFoundError
from diagnosis_engine import _parse_date, build_report
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Lightning Diagnosis MCP Service")


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

    # Fallback: try to parse a date string from additional_info.
    raw = additional_info.get("query_date") if isinstance(additional_info, dict) else None
    if isinstance(raw, str):
        return _parse_date(raw)

    # Last resort: try line_name in Chinese date form? No, fail fast.
    raise ValueError("缺少故障日期（fault_time 或 additional_info.query_date）")


def _extract_fault_type_and_confidence(report_markdown: str) -> tuple[str, float]:
    """Parse final conclusion and total confidence from the Markdown report.

    Args:
        report_markdown: Full Markdown report.

    Returns:
        Tuple of (fault_type, confidence).
    """
    # Final conclusion pattern supports both bold and plain text.
    # Examples:
    #   最终诊断结论为：**雷击-绕击**，综合置信度为0.985
    #   最终诊断结论为：雷击-绕击，综合置信度为0.985
    conclusion_match = re.search(
        r"最终诊断结论为：(?:\*\*)?(.+?)(?:\*\*)?\s*，\s*综合置信度为\s*([0-9.]+)",
        report_markdown,
        re.DOTALL,
    )
    if conclusion_match:
        fault_type = conclusion_match.group(1).strip()
        try:
            confidence = float(conclusion_match.group(2))
        except ValueError:
            confidence = 0.0
        return fault_type, confidence

    # Fallbacks.
    if "雷击-绕击" in report_markdown:
        return "雷击-绕击", 0.0
    if "雷击-反击" in report_markdown:
        return "雷击-反击", 0.0
    if "雷击" in report_markdown:
        return "雷击", 0.0
    if "非雷击" in report_markdown:
        return "非雷击", 0.0
    return "未知", 0.0


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "LightningDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    """Run the real lightning fault diagnosis for the given line and date."""
    client = APIClient()
    try:
        query_date = _extract_query_date(req.fault_time, req.additional_info or {})
        trip_record = await client.get_trip_info_data(query_date, req.line_name)
        trip_id = trip_record.trip_id
        diagnosis, info, ripple = await client.fetch_all_diagnosis_data(trip_id)
        report = build_report(diagnosis, info, ripple)

        fault_type, confidence = _extract_fault_type_and_confidence(report["markdown"])

        # Collect evidence lines from module results.
        evidence: list[str] = []
        for module in report.get("modules", []):
            if module.error:
                evidence.append(f"{module.title}: {module.error}")
            else:
                evidence.append(
                    f"{module.title}: {module.conclusion} (贡献 {module.contribution:.3f})"
                )

        # Encode images as base64 for downstream consumers.
        image_b64_list = [
            base64.b64encode(img).decode("utf-8") for img in report.get("images", [])
        ]

        structured_data = {
            "fault_type": fault_type,
            "confidence": confidence,
            "evidence": evidence,
            "details": {
                "query_date": query_date,
                "trip_id": trip_id,
                "province": trip_record.province,
                "voltage": trip_record.voltage,
                "images": image_b64_list,
                "module_scores": [
                    {
                        "title": m.title,
                        "conclusion": m.conclusion,
                        "support_score": m.support_score,
                        "weight": m.weight,
                        "contribution": m.contribution,
                    }
                    for m in report.get("modules", [])
                ],
            },
        }

        return DiagnoseResponse(
            tool_name="LightningDiagnosisTool",
            raw_text=report["markdown"],
            structured_data=structured_data,
            metadata={
                "source": "特高压雷电诊断系统",
                "data_quality": "real",
                "query_date": query_date,
            },
            timestamp=datetime.now(timezone.utc),
        )
    except DataNotFoundError as exc:
        logger.error(f"未找到记录: {exc.message}")
        raise HTTPException(status_code=404, detail=exc.message)
    except APIClientError as exc:
        logger.error(f"诊断失败: {exc.message}")
        raise HTTPException(status_code=500, detail=exc.message)
    except Exception as exc:
        logger.error(f"未知错误: {exc}")
        raise HTTPException(status_code=500, detail=f"诊断过程中发生未知错误: {exc}")
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
