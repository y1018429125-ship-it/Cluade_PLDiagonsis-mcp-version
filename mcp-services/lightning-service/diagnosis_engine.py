"""Diagnosis engine for the lightning fault HTTP service."""

from __future__ import annotations

import math
import re
from typing import Any

from config import DECIMAL_PLACES
from engine_models import (
    FlashRecord,
    ModuleResult,
    TripDiagnosisResponse,
    TripInfoResponse,
    TripRippleResponse,
    WeatherResponse,
)


def _format(value: float) -> str:
    """Format a float to the configured number of decimal places."""
    return f"{value:.{DECIMAL_PLACES}f}"


# Fixed weight labels shown with two decimal places per the document examples.
_WEIGHT_LABELS = {
    0.30: "0.30",
    0.15: "0.15",
    0.10: "0.10",
}


def _weight_label(weight: float) -> str:
    """Return a fixed-label weight string matching the requirement examples."""
    return _WEIGHT_LABELS.get(round(weight, 2), _format(weight))


def _parse_date(query_date: str) -> str:
    """Parse Chinese or ISO date into YYYY-MM-DD.

    Args:
        query_date: Date string like "2025-05-08" or "2025年5月8日".

    Returns:
        ISO format date string.
    """
    query_date = query_date.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", query_date):
        return query_date
    match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", query_date)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    raise ValueError(f"不支持的日期格式: {query_date}")


def _extract_process_conditions(process: str) -> tuple[str | None, str | None]:
    """Extract half-peak-time and amplitude conditions from process string.

    Args:
        process: The process string from getTripDiagnosis.

    Returns:
        Tuple of (half_peak_condition, amplitude_condition) or None.
    """
    cmp_map = {
        "远远小于": "<<",
        "远远大于": ">>",
        "小于等于": "≤",
        "大于等于": "≥",
        "小于": "<",
        "大于": ">",
    }

    half_peak_match = re.search(r"半峰值时间(.*?)(\d+(?:\.\d+)?)", process)
    half_peak_condition: str | None = None
    if half_peak_match:
        word = half_peak_match.group(1)
        num = half_peak_match.group(2)
        symbol = cmp_map.get(word, word)
        half_peak_condition = f"{symbol} {num}"

    amplitude_match = re.search(r"幅值(.*?)(\d+(?:\.\d+)?)", process)
    amplitude_condition: str | None = None
    if amplitude_match:
        word = amplitude_match.group(1)
        num = amplitude_match.group(2)
        symbol = cmp_map.get(word, word)
        amplitude_condition = f"{symbol} {num}"

    return half_peak_condition, amplitude_condition


def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great-circle distance between two coordinates in meters."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def analyze_module1(
    diagnosis: TripDiagnosisResponse,
    pressure: str,
) -> ModuleResult:
    """Analyze fault waveform evidence (module 1).

    Args:
        diagnosis: getTripDiagnosis response.
        pressure: Voltage level from getTripInfo.trip.pressure.

    Returns:
        Module result with markdown, score, and conclusion.
    """
    title = "模块一：故障波形分析"
    weight = 0.30

    if str(diagnosis.code) != "1001" or diagnosis.data is None or diagnosis.eigenvalue is None:
        return ModuleResult(
            title=title,
            markdown=f"## {title}\n\ngetTripDiagnosis 接口数据同步异常，该模块置信度贡献为 0。\n",
            support_score=0.0,
            weight=weight,
            contribution=0.0,
            conclusion="数据异常",
            error="getTripDiagnosis 接口数据同步异常",
        )

    data = diagnosis.data
    eigenvalue = diagnosis.eigenvalue

    is_lightning = data.is_lightning
    no_lightning = data.no_lightning
    round_pass = data.round_pass
    back_pass = data.back_pass

    # Determine conclusions.
    if is_lightning >= no_lightning:
        lightning_conclusion = "雷击"
        support_score = is_lightning
        if round_pass > back_pass:
            stroke_type_conclusion = "绕击"
            final_conclusion = "雷击-绕击"
        elif round_pass < back_pass:
            stroke_type_conclusion = "反击"
            final_conclusion = "雷击-反击"
        else:
            stroke_type_conclusion = ""
            final_conclusion = "雷击"
    else:
        lightning_conclusion = "非雷击"
        support_score = 0.0
        stroke_type_conclusion = ""
        final_conclusion = "非雷击"

    contribution = support_score * weight

    half_peak_condition, amplitude_condition = _extract_process_conditions(
        diagnosis.process or ""
    )

    # Build analysis sentence.
    if half_peak_condition:
        analysis_text = f"半峰值时间 {half_peak_condition}，符合{lightning_conclusion}判定条件"
    else:
        analysis_text = f"无法从 process 中提取半峰值时间条件，按概率判定为{lightning_conclusion}"

    if lightning_conclusion == "雷击" and round_pass != back_pass and amplitude_condition:
        analysis_text += (
            f"；电压等级为 {pressure}kV 且幅值 {amplitude_condition}，"
            f"符合{stroke_type_conclusion}判定条件"
        )

    markdown = f"""## {title}

### 波形分析

基于波形图分析得出，半峰值时间是 {eigenvalue.half_peak_time}，行波幅值是 {_format(eigenvalue.amplitude)}。判定分析：{analysis_text}。

### 概率分布

| 故障类型 | 总概率 | 雷击类型 | 雷击类型概率 |
|---|---|---|---|
| {lightning_conclusion} | {_format(is_lightning)} | 绕击 | {_format(round_pass)} |
| {lightning_conclusion} | {_format(is_lightning)} | 反击 | {_format(back_pass)} |
| 非雷击 | {_format(no_lightning)} | | |

### 故障波形分析结论

基于故障波形分析，输电线路故障类型为{final_conclusion}。

### 置信度贡献

权重 {_weight_label(weight)} × 支撑度 {_format(support_score)} = {_format(contribution)}
"""

    return ModuleResult(
        title=title,
        markdown=markdown,
        support_score=support_score,
        weight=weight,
        contribution=contribution,
        conclusion=final_conclusion,
    )


def analyze_module2(info: TripInfoResponse) -> ModuleResult:
    """Analyze distributed monitoring evidence (module 2)."""
    title = "模块二：分布式监测判定"
    weight = 0.15

    if str(info.code) != "1001" or info.trip is None:
        return ModuleResult(
            title=title,
            markdown=f"## {title}\n\ngetTripInfo 接口数据同步异常，该模块置信度贡献为 0。\n",
            support_score=0.0,
            weight=weight,
            contribution=0.0,
            conclusion="数据异常",
            error="getTripInfo 接口数据同步异常",
        )

    trip = info.trip
    support_score = 1.0 if "雷击" in (trip.trip_cause, trip.trip_class) else 0.0
    contribution = support_score * weight

    markdown = f"""## {title}

### 故障基本信息

- 故障时间：{trip.timedate}
- 线路名称：{trip.line_name}
- 电压等级：{trip.pressure} kV
- 故障类型：{trip.trip_cause}
- 故障相别：{trip.trip_phase}
- 故障杆塔位置：{trip.trip_station1} 的 {trip.trip_diaelepo1} 到 {trip.trip_station2} 的 {trip.trip_diaelepo2} 之间的 {trip.tower_id}号杆塔
- 故障描述：{trip.trip_description}

### 分布式监测结论

基于分布式监测系统，输电线路故障类型为{trip.trip_cause}，故障相别为{trip.trip_phase}。

### 置信度贡献

权重 {_weight_label(weight)} × 支撑度 {_format(support_score)} = {_format(contribution)}
"""

    return ModuleResult(
        title=title,
        markdown=markdown,
        support_score=support_score,
        weight=weight,
        contribution=contribution,
        conclusion=trip.trip_cause,
    )


def analyze_module3(info: TripInfoResponse) -> tuple[ModuleResult, ModuleResult]:
    """Analyze lightning location system evidence (module 3.1 and 3.2)."""
    title31 = "3.1：雷电活动规模"
    weight31 = 0.15
    title32 = "3.2：雷电活动定位"
    weight32 = 0.30

    if (
        str(info.code) != "1001"
        or info.trip is None
        or info.trip.longitude is None
        or info.trip.latitude is None
    ):
        result = ModuleResult(
            title="模块三：雷电定位系统分析",
            markdown=f"## {title31}\n\ngetTripInfo 接口数据同步异常，该模块置信度贡献为 0。\n\n## {title32}\n\ngetTripInfo 接口数据同步异常，该模块置信度贡献为 0。\n",
            support_score=0.0,
            weight=weight31 + weight32,
            contribution=0.0,
            conclusion="数据异常",
            error="getTripInfo 接口数据同步异常",
        )
        return result, result

    trip = info.trip
    flash_list = info.flash_list
    total_flash = len(flash_list)

    # 3.1 scoring.
    if total_flash == 0:
        score31 = 0.0
        activity_intensity = "无雷电活动"
    elif total_flash <= 3:
        score31 = 0.8
        activity_intensity = "有较高强度的雷电活动"
    else:
        score31 = 1.0
        activity_intensity = "有高强度的雷电活动"
    contribution31 = score31 * weight31

    # 3.2 scoring.
    nearby_records: list[dict[str, Any]] = []
    for flash in flash_list:
        try:
            dist = _haversine(
                flash.longitude, flash.latitude, trip.longitude, trip.latitude
            )
        except Exception:
            continue
        nearby_records.append(
            {
                "flash": flash,
                "distance": dist,
            }
        )

    nearby_records.sort(key=lambda r: r["distance"])
    within_500 = [r for r in nearby_records if r["distance"] <= 500.0]
    within_5000 = [r for r in nearby_records if r["distance"] <= 5000.0]

    if within_500:
        score32 = 1.0
        association_intensity = "有高强度的雷电活动"
    elif within_5000:
        score32 = 0.8
        association_intensity = "有较高强度的雷电活动"
    else:
        score32 = 0.0
        association_intensity = "无雷电活动"
    contribution32 = score32 * weight32

    # Build 3.1 table rows.
    flash_rows = "\n".join(
        f"| {flash.sequence} | {flash.timedate} | {flash.peak_current} | {flash.str_mltiplicity} | {flash.tower or ''} | {flash.distance or ''} | {flash.tdf_sum} | {flash.tdf_string} |"
        for flash in flash_list
    )

    # Build 3.2 table rows.
    geo_rows = "\n".join(
        f"| {r['flash'].timedate} | {r['flash'].peak_current} | {r['flash'].str_mltiplicity} | {trip.tower_id}号 | {int(round(r['distance']))} | {r['flash'].tdf_sum} | {r['flash'].tdf_string} |"
        for r in within_5000
    )

    nearest_text = ""
    if within_5000:
        nearest = within_5000[0]
        nearest_text = (
            f"其中，雷电时间为 {nearest['flash'].timedate}，"
            f"距离 {trip.tower_id}号 故障杆塔 {int(round(nearest['distance']))}m，"
            f"雷电流幅值为 {nearest['flash'].peak_current} kA。"
        )

    # Build time consistency comparison for module 3.2.
    ms_value = str(trip.milli_second or "")
    fault_time_ms = f"{trip.timedate} {ms_value}毫秒"
    nearest_time = nearest['flash'].timedate if within_5000 else ""
    fault_compare = f"{trip.timedate}.{ms_value.zfill(3)}"
    time_consistency = "一致" if within_5000 and fault_compare == nearest_time else "不一致"

    markdown31 = f"""## {title31}

雷电定位系统探测到，故障时刻前后一共有 {total_flash} 条雷电记录，表明该区域当时{activity_intensity}。

| 序号 | 时间 | 电流（kA） | 回击 | 最近杆塔 | 距离（m） | 站数 | 参与定位的探测站 |
|---|---|---|---|---|---|---|---|
{flash_rows}

### 置信度贡献

权重 {_weight_label(weight31)} × 支撑度 {_format(score31)} = {_format(contribution31)}
"""

    markdown32 = f"""## {title32}

雷电定位系统探测到，{trip.tower_id}号 故障杆塔附近 5000m 内一共有 {len(within_5000)} 条雷电记录。

{nearest_text}

表明 {trip.tower_id}号 故障杆塔附近当时{association_intensity}。

分布式监测系统数据显示，线路故障时间为 {fault_time_ms}，与雷电活动记录时间{time_consistency}。

| 时间 | 电流（kA） | 回击 | 故障杆塔 | 距离（m） | 站数 | 参与定位的探测站 |
|---|---|---|---|---|---|---|
{geo_rows}

### 置信度贡献

权重 {_weight_label(weight32)} × 支撑度 {_format(score32)} = {_format(contribution32)}
"""

    result31 = ModuleResult(
        title=title31,
        markdown=markdown31,
        support_score=score31,
        weight=weight31,
        contribution=contribution31,
        conclusion=activity_intensity,
    )
    result32 = ModuleResult(
        title=title32,
        markdown=markdown32,
        support_score=score32,
        weight=weight32,
        contribution=contribution32,
        conclusion=association_intensity,
    )
    return result31, result32


def analyze_module4(weather: WeatherResponse) -> ModuleResult:
    """Analyze weather conditions (module 4)."""
    title = "模块四：微气象"
    weight = 0.10

    if (
        str(weather.code) != "1001"
        or weather.data is None
        or weather.data.real is None
    ):
        return ModuleResult(
            title=title,
            markdown=f"## {title}\n\ngetWeather 接口数据同步异常，该模块置信度贡献为 0。\n",
            support_score=0.0,
            weight=weight,
            contribution=0.0,
            conclusion="数据异常",
            error="getWeather 接口数据同步异常",
        )

    real = weather.data.real
    hum = real.hum
    tmp = real.tmp
    ws = real.ws

    if hum > 70.0:
        support_score = 1.0
        conclusion_text = "空气极为潮湿，有利于雷暴形成条件"
    elif hum >= 40.0:
        support_score = 0.8
        conclusion_text = "空气较为潮湿，符合雷暴形成条件"
    else:
        support_score = 0.0
        conclusion_text = "空气干燥，不符合雷暴形成条件"

    contribution = support_score * weight

    markdown = f"""## {title}

### 故障时刻微气象信息

- 温度：{_format(tmp)} °C
- 风速：{_format(ws)} m/s
- 湿度：{_format(hum)}%

### 微气象分析

该区域故障时刻湿度为 **{_format(hum)}%**，{conclusion_text}。

### 置信度贡献

权重 {_weight_label(weight)} × 支撑度 {_format(support_score)} = {_format(contribution)}
"""

    return ModuleResult(
        title=title,
        markdown=markdown,
        support_score=support_score,
        weight=weight,
        contribution=contribution,
        conclusion=conclusion_text,
    )


def build_report(
    diagnosis: TripDiagnosisResponse,
    info: TripInfoResponse,
    ripple: TripRippleResponse,
    weather: WeatherResponse,
) -> dict[str, Any]:
    """Build the complete diagnosis report.

    Args:
        diagnosis: getTripDiagnosis response.
        info: getTripInfo response.
        ripple: getTripRipple response.
        weather: getWeather response.

    Returns:
        Dict with markdown report, images, total confidence, and modules.
    """
    pressure = info.trip.pressure if info.trip else ""
    module1 = analyze_module1(diagnosis, pressure)
    module2 = analyze_module2(info)
    module31, module32 = analyze_module3(info)
    module4 = analyze_module4(weather)

    modules = [module1, module2, module31, module32, module4]
    total_confidence = sum(m.contribution for m in modules)
    final_conclusion = module1.conclusion

    summary = f"""### 综合诊断结论

- 模块一（故障波形分析）：{module1.conclusion}，置信度贡献 {_format(module1.contribution)}
- 模块二（分布式监测判定）：{module2.conclusion}，置信度贡献 {_format(module2.contribution)}
- 模块三3.1（雷电活动规模）：{module31.conclusion}，置信度贡献 {_format(module31.contribution)}
- 模块三3.2（雷电活动定位）：{module32.conclusion}，置信度贡献 {_format(module32.contribution)}
- 模块四（微气象）：{module4.conclusion}，置信度贡献 {_format(module4.contribution)}

基于 5 个证据条目的交叉验证，最终诊断结论为：{final_conclusion}，综合置信度为{_format(total_confidence)}
"""

    markdown = (
        f"# 雷电故障诊断报告\n\n{module1.markdown}\n\n{module2.markdown}\n\n"
        f"## 模块三：雷电定位系统分析\n\n{module31.markdown}\n\n{module32.markdown}\n\n"
        f"{module4.markdown}\n\n{summary}"
    )

    # Prepare images only when module 1 has data.
    from wave_plotter import plot_waveforms

    images: list[bytes] = []
    if str(ripple.code) == "1001" and ripple.data:
        images = plot_waveforms(ripple)

    return {
        "markdown": markdown,
        "images": images,
        "total_confidence": total_confidence,
        "final_conclusion": final_conclusion,
        "modules": modules,
    }
