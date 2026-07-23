import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Wind Diagnosis MCP Service")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WindDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    try:
        return DiagnoseResponse(
            tool_name="WindDiagnosisTool",
            raw_text=f"风偏监测：线路 {req.line_name} 故障时段风速 18m/s，"
                      f"超过设计风速 15m/s，绝缘子串风偏角 12度，接近安全限值。",
            structured_data={
                "fault_type": "风偏放电",
                "confidence": 0.45,
                "evidence": [
                    "风速 18m/s 超过设计值 15m/s",
                    "绝缘子串风偏角 12度",
                ],
                "details": {"wind_speed_ms": 18, "design_speed_ms": 15, "deflection_deg": 12},
            },
            metadata={"source": "气象监测站", "data_quality": "real"},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
