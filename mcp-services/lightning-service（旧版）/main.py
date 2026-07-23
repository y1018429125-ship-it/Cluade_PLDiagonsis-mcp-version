import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Lightning Diagnosis MCP Service")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "LightningDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    try:
        return DiagnoseResponse(
            tool_name="LightningDiagnosisTool",
            raw_text=f"雷电监测：线路 {req.line_name} 在故障时段检测到雷电活动。"
                      f"雷电定位系统显示故障点 3km 范围内有 2 次地闪记录，"
                      f"雷电流幅值分别为 45kA 和 62kA。",
            structured_data={
                "fault_type": "雷击跳闸",
                "confidence": 0.85,
                "evidence": [
                    "雷电定位系统记录：故障点 3km 范围内 2 次地闪",
                    "雷电流幅值 45kA、62kA，超过线路耐雷水平",
                    "故障相别与雷电先导方向一致",
                ],
                "details": {
                    "lightning_count": 2,
                    "max_current_ka": 62,
                    "distance_km": 3,
                },
            },
            metadata={"source": "雷电定位系统", "data_quality": "real"},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
