from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tool_name"] == "WeatherDiagnosisTool"

def test_diagnose():
    response = client.post("/diagnose", json={"line_name": "武汉线", "voltage_level": "220kV"})
    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "WeatherDiagnosisTool"
    assert "structured_data" in data
    assert data["structured_data"]["fault_type"] == "气象相关故障"
