## 调用记录 — 2026-08-14 14:45:06 UTC+08:00

### 请求

```json
{
  "line_name": "雅湖线",
  "voltage_level": "",
  "fault_time": "2025-05-08T00:00:00",
  "additional_info": {
    "line_id": "sess_e15fb270",
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

## 气象诊断

### 故障时刻气象信息

- 温度：26.130 °C
- 湿度：80.161%

### 气象分析

该区域故障时刻湿度为 **80.161%**，空气极为潮湿，有利于雷暴形成条件。


#### structured_data

```json
{
  "temperature_c": 26.1303,
  "humidity_pct": 80.1612,
  "humidity_description": "空气极为潮湿，有利于雷暴形成条件",
  "details": {
    "query_date": "2025-05-08",
    "trip_id": "S_Y202505080552"
  }
}
```

#### metadata

```json
{
  "source": "特高压气象数据",
  "data_quality": "real",
  "query_date": "2025-05-08"
}
```

---
