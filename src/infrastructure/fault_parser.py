"""故障信息解析器

从用户输入中提取结构化故障上下文。
支持规则匹配和 LLM 辅助解析。
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from src.core.models import FaultContext
from src.infrastructure.line_normalizer import LineNormalizer

logger = logging.getLogger(__name__)


class FaultContextParser:
    """故障上下文解析器"""

    # 杆塔号模式
    TOWER_PATTERNS = [
        re.compile(r"[#第]?(\d+)[号]?[杆塔基]"),
        re.compile(r"[杆塔基][号]?\s*(\d+)"),
    ]

    # 故障类型关键词
    FAULT_KEYWORDS: Dict[str, list[str]] = {
        "lightning": ["雷击", "雷电", "闪电", "雷害"],
        "icing": ["覆冰", "结冰", "冰害", "冻雨"],
        "wind": ["风偏", "大风", "强风", "台风", "风害"],
        "bird": ["鸟害", "鸟粪", "鸟巢", "鸟类"],
        "pollution": ["污闪", "污秽", "污染"],
        "foreign": ["外破", "外力破坏", "异物", "施工"],
    }

    # 时间模式
    TIME_PATTERNS = [
        # 2024-06-15 14:30:00.123 or 2024-06-15 14:30:00 or 2024-06-15 14:30
        re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.(\d{3}))?"),
        # 2024年6月15日14时30分 / 2024年6月15日14点30分
        re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[时点](\d{1,2})分?"),
        # 6月15日14:30
        re.compile(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})"),
        # 2024年6月15日 / 2024-06-15 / 2024/06/15（纯日期，默认 00:00:00）
        re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
        re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\s*\d{1,2}[时点:])(?!\s*\d{1,2}:\d{2})"),
        # 6月15日（纯日期，默认 00:00:00，使用当年）
        re.compile(r"(\d{1,2})月(\d{1,2})日(?!\s*\d{1,2}[时点:])(?!\s*\d{1,2}:\d{2})"),
        # 今天、昨天、前天
        re.compile(r"(今天|昨天|前天)"),
    ]

    # 天气模式
    WEATHER_PATTERNS: Dict[str, list[str]] = {
        "condition": ["晴", "阴", "多云", "小雨", "中雨", "大雨", "雷阵雨", "雪", "雾", "霾"],
        "temperature": re.compile(r"气温\s*[:：]?\s*(-?\d+\.?\d*)\s*[°度]?[Cc]"),
        "wind": re.compile(r"风速\s*[:：]?\s*(\d+\.?\d*)\s*[m米]?[/s秒]?"),
        "humidity": re.compile(r"湿度\s*[:：]?\s*(\d+\.?\d*)\s*%?"),
    }

    @classmethod
    def parse(cls, message: str, session_line_name: str = "") -> FaultContext:
        """从用户消息中解析故障上下文"""
        logger.debug(f"解析故障信息: {message[:100]}...")

        # 提取线路名称
        line_name, voltage = cls._extract_line_name(message, session_line_name)

        # 提取杆塔号
        tower_id = cls._extract_tower_id(message)

        # 提取故障时间
        fault_time = cls._extract_fault_time(message)

        # 提取天气信息
        weather_info = cls._extract_weather(message)

        # 提取故障类型
        fault_types = cls._detect_fault_types(message)

        # 提取 SCADA 数据（如果有）
        scada_data = cls._extract_scada_data(message)

        # 提取波行数据引用
        wave_data = cls._extract_wave_data(message)

        return FaultContext(
            line_id="",  # 由调用方填充
            line_name=line_name or session_line_name,
            tower_id=tower_id,
            fault_time=fault_time,
            weather_info=weather_info,
            scada_data=scada_data,
            wave_data=wave_data,
            additional_info={
                "user_input": message,
                "detected_fault_types": fault_types,
                "voltage_level": voltage,
            },
        )

    # 常见误匹配词（不应被视为线路名）
    INVALID_LINE_PREFIXES = {"没有", "这是", "那个", "一条", "所有", "什么", "我们", "你们"}

    @classmethod
    def _extract_line_name(cls, message: str, fallback: str = "") -> Tuple[str, str]:
        """提取线路名称和电压等级"""
        # 匹配 "220kV京西线" 格式
        match = re.search(r"(\d+kV)\s*([^，,。\s]{2,10}[线线路])", message)
        if match:
            return LineNormalizer.normalize(match.group(2)), match.group(1)

        # 匹配纯线路名，要求前面是句首或分隔符
        match = re.search(r"(?:^|[，,。；;\s])([^，,。\s]{2,8}[线线路])", message)
        if match:
            line_name = LineNormalizer.normalize(match.group(1))
            # 过滤明显不合理的匹配
            if not any(line_name.startswith(p) for p in cls.INVALID_LINE_PREFIXES):
                return line_name, ""

        return fallback, ""

    @classmethod
    def _extract_tower_id(cls, message: str) -> Optional[str]:
        """提取杆塔号"""
        for pattern in cls.TOWER_PATTERNS:
            match = pattern.search(message)
            if match:
                return f"T-{match.group(1)}"
        return None

    @classmethod
    def _extract_fault_time(cls, message: str) -> Optional[datetime]:
        """提取故障时间"""
        # 尝试标准日期时间格式
        for pattern in cls.TIME_PATTERNS:
            match = pattern.search(message)
            if not match:
                continue

            groups = match.groups()

            # 处理相对时间
            if groups[0] in ("今天", "昨天", "前天"):
                now = datetime.now()
                if groups[0] == "今天":
                    return now.replace(hour=12, minute=0, second=0, microsecond=0)
                elif groups[0] == "昨天":
                    return (now - timedelta(days=1)).replace(
                        hour=12, minute=0, second=0, microsecond=0
                    )
                else:
                    return (now - timedelta(days=2)).replace(
                        hour=12, minute=0, second=0, microsecond=0
                    )

            # 解析绝对时间
            try:
                # 纯日期格式（无时分），默认 00:00:00
                if len(groups) == 3 and groups[0] and groups[0].isdigit() and len(groups[0]) == 4:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    return datetime(year, month, day, 0, 0, 0)
                if len(groups) == 2 and groups[0] and groups[0].isdigit() and 1 <= len(groups[0]) <= 2:
                    # 月/日 纯日期格式，使用当年
                    now = datetime.now()
                    month, day = int(groups[0]), int(groups[1])
                    return datetime(now.year, month, day, 0, 0, 0)
                if len(groups) >= 6 and groups[0] and groups[0].isdigit() and len(groups[0]) == 4:
                    # 2024-06-15 14:30:00
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute = int(groups[3]), int(groups[4])
                    second = int(groups[5]) if groups[5] else 0
                    # Only the first TIME_PATTERN captures milliseconds (group 6)
                    microsecond = int(groups[6]) * 1000 if len(groups) > 6 and groups[6] else 0
                    return datetime(year, month, day, hour, minute, second, microsecond)
                elif len(groups) >= 5 and "年" in message:
                    # 2024年6月15日14时30分
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute = int(groups[3]), int(groups[4])
                    return datetime(year, month, day, hour, minute, 0)
                elif len(groups) >= 4:
                    # 6月15日14:30（使用当年）
                    now = datetime.now()
                    month, day = int(groups[0]), int(groups[1])
                    hour, minute = int(groups[2]), int(groups[3])
                    return datetime(now.year, month, day, hour, minute, 0)
            except (ValueError, IndexError):
                continue

        return None

    @classmethod
    def _extract_weather(cls, message: str) -> Optional[Dict[str, Any]]:
        """提取天气信息"""
        weather: Dict[str, Any] = {}

        # 匹配天气状况
        conditions = []
        for cond in cls.WEATHER_PATTERNS["condition"]:
            if cond in message:
                conditions.append(cond)
        if conditions:
            weather["condition"] = ",".join(conditions)

        # 匹配温度
        temp_match = cls.WEATHER_PATTERNS["temperature"].search(message)
        if temp_match:
            weather["temperature"] = float(temp_match.group(1))

        # 匹配风速
        wind_match = cls.WEATHER_PATTERNS["wind"].search(message)
        if wind_match:
            weather["wind_speed"] = float(wind_match.group(1))

        # 匹配湿度
        humidity_match = cls.WEATHER_PATTERNS["humidity"].search(message)
        if humidity_match:
            weather["humidity"] = float(humidity_match.group(1))

        return weather if weather else None

    @classmethod
    def _detect_fault_types(cls, message: str) -> list[str]:
        """检测可能的故障类型"""
        detected = []
        for fault_type, keywords in cls.FAULT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message:
                    detected.append(fault_type)
                    break
        return detected

    @classmethod
    def _extract_scada_data(cls, message: str) -> Optional[Dict[str, Any]]:
        """提取 SCADA 数据"""
        scada: Dict[str, Any] = {}

        # 电流
        current_match = re.search(r"电流\s*[:：]?\s*(\d+\.?\d*)\s*[Aa]", message)
        if current_match:
            scada["current"] = float(current_match.group(1))

        # 电压
        voltage_match = re.search(r"电压\s*[:：]?\s*(\d+\.?\d*)\s*[kK]?[vV]", message)
        if voltage_match:
            scada["voltage"] = float(voltage_match.group(1))

        # 功率
        power_match = re.search(r"功率\s*[:：]?\s*(\d+\.?\d*)\s*[Mm]?[Ww]", message)
        if power_match:
            scada["power"] = float(power_match.group(1))

        return scada if scada else None

    @classmethod
    def _extract_wave_data(cls, message: str) -> Optional[Dict[str, Any]]:
        """提取波行数据引用"""
        wave_refs = []

        # 匹配波行数据文件引用
        patterns = [
            re.compile(r"波行数据[:：]?\s*(\S+)"),
            re.compile(r"录波[:：]?\s*(\S+)"),
            re.compile(r"故障波形[:：]?\s*(\S+)"),
        ]

        for pattern in patterns:
            match = pattern.search(message)
            if match:
                wave_refs.append(match.group(1))

        if wave_refs:
            return {"references": wave_refs}

        return None
