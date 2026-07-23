"""线路名称标准化"""

import re


class LineNormalizer:
    """线路名称标准化器

    提取核心线路名，去掉电压等级、地区前缀等修饰。
    """

    # 电压等级前缀模式
    VOLTAGE_PATTERN = re.compile(r"^\d+kV", re.IGNORECASE)

    # 常见前缀
    PREFIXES = ["220kV", "110kV", "500kV", "35kV", "10kV"]

    @classmethod
    def normalize(cls, line_name: str) -> str:
        """标准化线路名称

        示例：
            "220kV京西线" -> "京西线"
            "110kV武昌线" -> "武昌线"
        """
        name = line_name.strip()

        # 去掉电压等级前缀
        for prefix in cls.PREFIXES:
            if name.upper().startswith(prefix.upper()):
                name = name[len(prefix):]
                break

        # 去掉其他数字前缀
        name = re.sub(r"^\d+[kK][vV]", "", name)

        return name.strip()

    @classmethod
    def extract_voltage(cls, line_name: str) -> str:
        """提取电压等级"""
        match = cls.VOLTAGE_PATTERN.search(line_name)
        return match.group(0) if match else ""
