## 调用记录 — 2026-07-20 09:58:12 UTC+08:00

### 请求

```json
{
  "line_name": "雅湖线",
  "voltage_level": "",
  "fault_time": "2025-05-08T00:00:00",
  "additional_info": {
    "line_id": "sess_55f9646e",
    "tower_id": null,
    "weather_info": null,
    "scada_data": null,
    "wave_data": null,
    "images": null,
    "user_input": "雅湖线2025年5月8日情况",
    "detected_fault_types": [],
    "voltage_level": ""
  }
}
```

### 响应

#### raw_text

风偏监测：线路 雅湖线 故障时段风速 18m/s，超过设计风速 15m/s，绝缘子串风偏角 12度，接近安全限值。

#### structured_data

```json
{
  "fault_type": "风偏放电",
  "confidence": 0.45,
  "evidence": [
    "风速 18m/s 超过设计值 15m/s",
    "绝缘子串风偏角 12度"
  ],
  "details": {
    "wind_speed_ms": 18,
    "design_speed_ms": 15,
    "deflection_deg": 12
  }
}
```

#### metadata

```json
{
  "source": "气象监测站",
  "data_quality": "real"
}
```

---
