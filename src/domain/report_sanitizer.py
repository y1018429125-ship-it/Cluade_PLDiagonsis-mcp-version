"""报告 LaTeX 清洗器

LLM 生成的诊断报告中可能残留 LaTeX 行内公式（$...$）。
前端渲染器（marked-katex-extension）对紧贴中文字符的 $ 无法渲染，
导致用户看到原始 LaTeX 源码（乱码）。
本模块在报告入库前将 $...$ 公式确定性地转换为纯文本符号。

设计约束：
- 纯 Python 正则实现，无第三方依赖
- 幂等：无 LaTeX 的文本原样返回；重复执行结果不变
- 不影响 Markdown 表格、标题等结构
"""

import re

# 行内/块级公式：$...$ 或 $$...$$
_MATH_RE = re.compile(r"\$+([^$]+)\$+")

# \text{...} 等文本包装命令 → 取花括号内容
_TEXT_CMD_RE = re.compile(r"\\(?:text|mathrm|mathbf|mathit|mathsf|textbf)\{([^{}]*)\}")

# 已知符号命令映射（正则 alternation 按长度降序，避免 \le 吃掉 \leq）
_SYMBOL_MAP = {
    "approx": "≈",
    "times": "×",
    "cdot": "·",
    "circ": "°",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "le": "≤",
    "ge": "≥",
    "ne": "≠",
    "pm": "±",
}
_SYMBOL_CMD_RE = re.compile(
    r"\\(approx|times|cdot|circ|leq|geq|neq|le|ge|ne|pm)(?![a-zA-Z])|\\%"
)

# ^{...} 上标写法
_CARET_BRACE_RE = re.compile(r"\^\{([^{}]*)\}")

# 未知字母命令兜底：去反斜杠保留字母（如 \foo → foo）
_UNKNOWN_CMD_RE = re.compile(r"\\([a-zA-Z]+)")

# 残留花括号
_BRACES_RE = re.compile(r"[{}]")


def _latex_to_text(expr: str) -> str:
    """将单个 LaTeX 表达式转换为纯文本。"""
    s = expr
    # 1. 已知符号命令映射（\times→×、\le→≤、\circ→°、\%→% 等）
    #    必须先于 \text 替换：^\circ\text{C} 若先拆 \text，\circ 后跟字母 C
    #    会触碰边界保护导致无法识别
    s = _SYMBOL_CMD_RE.sub(
        lambda m: "%" if m.group(1) is None else _SYMBOL_MAP[m.group(1)], s
    )
    # 2. \text{...} 类命令取内容
    s = _TEXT_CMD_RE.sub(lambda m: m.group(1), s)
    # 3. 上标归一化：^{...} → 内容；^° → °（由 ^\circ 转换而来）；孤立 ^ 删除
    s = _CARET_BRACE_RE.sub(lambda m: m.group(1), s)
    s = s.replace("^°", "°")
    s = s.replace("^", "")
    # 4. 未知命令兜底去反斜杠
    s = _UNKNOWN_CMD_RE.sub(lambda m: m.group(1), s)
    # 5. 清除残留花括号
    s = _BRACES_RE.sub("", s)
    return s.strip()


def sanitize_report(text: str) -> str:
    """清洗报告文本中的 LaTeX 公式，转换为纯文本。

    Args:
        text: LLM 生成的报告 Markdown 文本。

    Returns:
        清洗后的文本。无 $ 的文本原样返回（幂等）。
    """
    if not text or "$" not in text:
        return text
    return _MATH_RE.sub(lambda m: _latex_to_text(m.group(1)), text)
