## 调用记录 — 2026-08-10 14:13:41 UTC+08:00

### 请求

```json
{
  "line_name": "雅湖线",
  "voltage_level": "",
  "fault_time": "2025-05-08T19:46:00",
  "additional_info": {
    "line_id": "sess_ce263a85",
    "tower_id": null,
    "weather_info": null,
    "scada_data": null,
    "wave_data": null,
    "images": null,
    "user_input": "雅湖线2025年5月8日19时46分发生故障，请进行诊断",
    "detected_fault_types": [],
    "voltage_level": ""
  }
}
```

### 响应

#### raw_text

鸟害监测：线路 雅湖线 区段鸟类活动记录正常，无鸟粪闪络痕迹，绝缘子表面清洁。

#### structured_data

```json
{
  "fault_type": "鸟害故障",
  "confidence": 0.2,
  "evidence": [
    "无鸟粪闪络痕迹",
    "绝缘子表面清洁",
    "鸟类活动记录正常"
  ],
  "details": {
    "bird_activity": "normal",
    "contamination_level": "low"
  }
}
```

#### metadata

```json
{
  "source": "巡检记录",
  "data_quality": "real"
}
```

---
