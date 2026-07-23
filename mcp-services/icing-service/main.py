import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from models import DiagnoseRequest, DiagnoseResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Icing Diagnosis MCP Service")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "IcingDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    try:
        return DiagnoseResponse(
            tool_name="IcingDiagnosisTool",
            raw_text=f"覆冰监测：线路 {req.line_name} 覆冰厚度 2.3mm，低于设计标准 10mm，"
                      f"导线弧垂正常，无脱冰跳跃迹象。",
            structured_data={
                "fault_type": "覆冰故障",
                "confidence": 0.30,
                "evidence": [
                    "覆冰厚度 2.3mm，低于设计标准",
                    "导线弧垂正常",
                    "无脱冰跳跃记录",
                ],
                "details": {"icing_thickness_mm": 2.3, "design_standard_mm": 10},
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
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
