import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tool_name"] == "LightningDiagnosisTool"


def test_diagnose():
    response = client.post(
        "/diagnose", json={"line_name": "武汉线", "voltage_level": "220kV"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "LightningDiagnosisTool"
    assert "structured_data" in data
    assert data["structured_data"]["fault_type"] == "雷击跳闸"
    assert "timestamp" in data
