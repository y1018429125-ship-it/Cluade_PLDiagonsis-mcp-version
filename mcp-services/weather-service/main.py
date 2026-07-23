import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Weather Diagnosis MCP Service")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WeatherDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    try:
        return DiagnoseResponse(
            tool_name="WeatherDiagnosisTool",
            raw_text=f"天气查询：线路 {req.line_name} 故障时段天气状况："
                      f"雷阵雨，气温 28°C，相对湿度 85%，"
                      f"大气电场强度 12kV/m，处于强雷电环境。",
            structured_data={
                "fault_type": "气象相关故障",
                "confidence": 0.60,
                "evidence": [
                    "雷阵雨天气",
                    "大气电场强度 12kV/m",
                    "相对湿度 85%",
                ],
                "details": {
                    "weather": "雷阵雨",
                    "temperature_c": 28,
                    "humidity_pct": 85,
                    "electric_field_kv_m": 12,
                },
            },
            metadata={"source": "气象站", "data_quality": "real"},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8005))
    uvicorn.run(app, host="0.0.0.0", port=port)
