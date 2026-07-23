"""Tests for src/infrastructure/line_normalizer.py — name normalization and voltage extraction."""

import pytest

from src.infrastructure.line_normalizer import LineNormalizer


# ============================================================================
# normalize — voltage prefix removal
# ============================================================================


def test_normalize_strips_220kv_prefix() -> None:
    """normalize() removes '220kV' prefix."""
    assert LineNormalizer.normalize("220kV京西线") == "京西线"


def test_normalize_strips_110kv_prefix() -> None:
    """normalize() removes '110kV' prefix."""
    assert LineNormalizer.normalize("110kV武昌线") == "武昌线"


def test_normalize_strips_500kv_prefix() -> None:
    """normalize() removes '500kV' prefix."""
    assert LineNormalizer.normalize("500kV华北线") == "华北线"


def test_normalize_strips_35kv_prefix() -> None:
    """normalize() removes '35kV' prefix."""
    assert LineNormalizer.normalize("35kV城东线") == "城东线"


def test_normalize_strips_10kv_prefix() -> None:
    """normalize() removes '10kV' prefix."""
    assert LineNormalizer.normalize("10kV城南线") == "城南线"


def test_normalize_strips_lowercase_prefix() -> None:
    """normalize() handles lowercase 'kv' variants."""
    assert LineNormalizer.normalize("220kv京西线") == "京西线"


def test_normalize_strips_mixed_case_prefix() -> None:
    """normalize() handles mixed-case 'kV' variants."""
    assert LineNormalizer.normalize("220Kv京西线") == "京西线"


def test_normalize_strips_arbitrary_voltage_prefix() -> None:
    """normalize() removes any \d+kV prefix via regex fallback."""
    assert LineNormalizer.normalize("750kV超高压线") == "超高压线"
    assert LineNormalizer.normalize("1000KV特高压线") == "特高压线"


def test_normalize_preserves_name_without_prefix() -> None:
    """normalize() leaves clean names untouched."""
    assert LineNormalizer.normalize("京西线") == "京西线"


def test_normalize_trims_whitespace() -> None:
    """normalize() strips leading and trailing whitespace."""
    assert LineNormalizer.normalize("  220kV京西线  ") == "京西线"


def test_normalize_handles_empty_string() -> None:
    """normalize() returns empty string for empty input."""
    assert LineNormalizer.normalize("") == ""


def test_normalize_handles_prefix_only() -> None:
    """normalize() returns empty string when input is just a prefix."""
    assert LineNormalizer.normalize("220kV") == ""


# ============================================================================
# extract_voltage
# ============================================================================


def test_extract_voltage_finds_220kv() -> None:
    """extract_voltage() returns '220kV' from a prefixed name."""
    assert LineNormalizer.extract_voltage("220kV京西线") == "220kV"


def test_extract_voltage_finds_110kv() -> None:
    """extract_voltage() returns '110kV' from a prefixed name."""
    assert LineNormalizer.extract_voltage("110kV武昌线") == "110kV"


def test_extract_voltage_is_case_insensitive() -> None:
    """extract_voltage() matches regardless of case."""
    assert LineNormalizer.extract_voltage("220kv京西线") == "220kv"
    assert LineNormalizer.extract_voltage("220KV京西线") == "220KV"


def test_extract_voltage_returns_empty_when_no_match() -> None:
    """extract_voltage() returns '' for names without voltage prefix."""
    assert LineNormalizer.extract_voltage("京西线") == ""


def test_extract_voltage_returns_empty_for_empty_string() -> None:
    """extract_voltage() returns '' for empty input."""
    assert LineNormalizer.extract_voltage("") == ""


def test_extract_voltage_only_matches_at_start() -> None:
    """extract_voltage() matches only at the start of the string."""
    assert LineNormalizer.extract_voltage("线路220kV京西") == ""
    assert LineNormalizer.extract_voltage("220kV京西") == "220kV"
