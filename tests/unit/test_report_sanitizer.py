"""report_sanitizer 单元测试

测试用例全部来自 logs/diagnosis/ 历史诊断报告中的真实 LaTeX 样本。
"""

import asyncio

import pytest

from src.domain.report_sanitizer import sanitize_report


class TestInlineMathConversion:
    """历史日志中出现的真实 LaTeX 样本（23 行失败用例的代表）。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # 加权置信度计算（最高频）
            ("$0.985 \\times 1.0$", "0.985 × 1.0"),
            ("$0.45 \\times 0.8$", "0.45 × 0.8"),
            ("$0.2 \\times 0.6$", "0.2 × 0.6"),
            ("$0.985 \\times 1.0 = 0.985$", "0.985 × 1.0 = 0.985"),
            ("$0.0 (\\text{confidence}) \\times 1.0 (\\text{weight}) = 0.0$",
             "0.0 (confidence) × 1.0 (weight) = 0.0"),
            # 数值单位
            ("$19.6\\text{kA}$", "19.6kA"),
            ("$26.13^\\circ\\text{C}$", "26.13°C"),
            ("$\\pm 800\\text{kV}$", "± 800kV"),
            ("$80.161\\%$", "80.161%"),
            ("$18\\text{m/s}$", "18m/s"),
            ("$15\\text{m/s}$", "15m/s"),
            ("$5000\\text{m}$", "5000m"),
            ("$12^\\circ$", "12°"),
            # 比较符
            ("$\\le 40$", "≤ 40"),
            ("$\\ge 5^\\circ\\text{C}$", "≥ 5°C"),
            ("$\\text{Max} = 0.0$", "Max = 0.0"),
            # 纯数字
            ("$0.000564$", "0.000564"),
            ("$-2262.590$", "-2262.590"),
            ("$0.95$", "0.95"),
            ("$1.0$", "1.0"),
            ("$19:46:30.056$", "19:46:30.056"),
        ],
    )
    def test_real_samples(self, raw, expected):
        assert sanitize_report(raw) == expected

    def test_composite_sentence(self):
        raw = "实测风速$18\\text{m/s} >$ 设计风速$15\\text{m/s}$"
        assert sanitize_report(raw) == "实测风速18m/s > 设计风速15m/s"

    def test_latex_after_cjk_punctuation(self):
        raw = "**雷击诊断**：$0.0 \\times 1.0 = 0.0$"
        assert sanitize_report(raw) == "**雷击诊断**：0.0 × 1.0 = 0.0"

    def test_bold_wrapped_math(self):
        assert sanitize_report("**$0.985$**") == "**0.985**"

    def test_table_row_preserved(self):
        raw = "| **LightningDiagnosisTool** | 0.985 | 1.0 | $0.985 \\times 1.0$ | **0.985** |"
        assert sanitize_report(raw) == (
            "| **LightningDiagnosisTool** | 0.985 | 1.0 | 0.985 × 1.0 | **0.985** |"
        )

    def test_block_dollar(self):
        assert sanitize_report("$$0.985 \\times 1.0$$") == "0.985 × 1.0"


class TestFallback:
    """未知命令兜底与边界情况。"""

    def test_unknown_command_strips_backslash(self):
        assert sanitize_report("$\\foo 123$") == "foo 123"

    def test_frac_fallback(self):
        # 未实现 \frac 专门转换，兜底去掉反斜杠和花括号
        assert sanitize_report("$\\frac{1}{2}$") == "frac12"

    def test_superscript_braces(self):
        assert sanitize_report("$2^{10}$") == "210"

    def test_empty_math(self):
        # $$ 之间无内容不匹配，原样返回
        assert sanitize_report("$$") == "$$"


class TestIdempotency:
    """幂等性：无 LaTeX 文本原样返回，重复清洗结果不变。"""

    def test_plain_text_unchanged(self):
        text = "# 报告\n\n半峰值时间 ≤ 40，风速 18m/s，温度 26.13°C"
        assert sanitize_report(text) == text

    def test_empty_and_none(self):
        assert sanitize_report("") == ""
        assert sanitize_report(None) is None

    def test_double_sanitize(self):
        raw = "**雷击诊断**：$0.985 \\times 1.0$，温度$26.13^\\circ\\text{C}$"
        once = sanitize_report(raw)
        assert sanitize_report(once) == once
        assert "$" not in once
        assert "\\" not in once

    def test_no_dollar_fast_path(self):
        text = "没有任何公式的报告内容 × ≤ ≥ ° ±"
        assert sanitize_report(text) is text


class TestComposerIntegration:
    """验证清洗模块在报告生成链路中真正生效（接入点测试）。"""

    def test_format_response_sanitizes(self):
        from src.domain.report_composer import ReportComposer

        composer = ReportComposer(llm_service=None)
        out = composer._format_response("**雷击诊断**：$0.985 \\times 1.0$")
        assert "$" not in out
        assert "\\" not in out
        assert "0.985 × 1.0" in out

    def test_compose_with_mock_llm(self):
        from src.core.models import ToolOutput
        from src.domain.report_composer import ReportComposer

        class FakeLLM:
            async def chat(self, messages):
                return (
                    "# 输电线路故障诊断报告\n\n"
                    "## 诊断结论\n\n"
                    "加权计算：$0.985 \\times 1.0 = 0.985$\n\n"
                    "故障时刻温度$26.13^\\circ\\text{C}$，湿度$80.161\\%$"
                )

        composer = ReportComposer(llm_service=FakeLLM())
        tool_outputs = {
            "LightningDiagnosisTool": ToolOutput(
                tool_name="LightningDiagnosisTool",
                raw_text="雷电定位：判定为雷击",
                structured_data={"fault_type": "雷击-绕击", "confidence": 0.985},
            )
        }
        result = asyncio.run(
            composer.compose(tool_outputs, None, "sess_test_sanitize")
        )
        report = result["report"]
        assert "$" not in report
        assert "\\" not in report
        assert "0.985 × 1.0 = 0.985" in report
        assert "26.13°C" in report
