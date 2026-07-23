"""Waveform plotter for the lightning diagnosis HTTP service."""

from __future__ import annotations

import io
import os
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

from config import WAVE_IMAGE_HEIGHT, WAVE_IMAGE_WIDTH

# Try to load a Chinese font; fall back to DejaVu Sans if not available.
_CHINESE_FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

for _font_path in _CHINESE_FONT_PATHS:
    if os.path.exists(_font_path):
        font_manager.fontManager.addfont(_font_path)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=_font_path).get_name()
        plt.rcParams["axes.unicode_minus"] = False
        break
from engine_models import TripRippleResponse


# Fixed axis ranges matching the mock front-end SVG.
AXIS_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "行波1": {"x": (0.0, 7000.0), "y": (-2000.0, 1000.0)},
    "行波2": {"x": (0.0, 7000.0), "y": (-3000.0, 2000.0)},
    "工频": {"x": (0.0, 1200.0), "y": (-2000.0, 5000.0)},
}

Y_TICKS: dict[str, list[float]] = {
    "行波1": [-2000.0, -1500.0, -1000.0, -500.0, 0.0, 500.0, 1000.0],
    "行波2": [-3000.0, -2000.0, -1000.0, 0.0, 1000.0, 2000.0],
    "工频": [-2000.0, -1000.0, 0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
}

X_TICKS: dict[str, list[float]] = {
    "行波": [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 7000.0],
    "工频": [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 1100.0, 1200.0],
}

COLORS = {
    "wave_line": "#2196F3",
    "grid": "#e0e0e0",
    "axis": "#333333",
    "tick_label": "#666666",
    "label": "#555555",
}

FONT_SIZES = {"tick": 8, "label": 10, "title": 11}


def _map_x(raw_x: np.ndarray, wave_type: str, index: int) -> np.ndarray:
    """Map raw x coordinates to the display range.

    Args:
        raw_x: Raw x values from the API.
        wave_type: "行波" or "工频".
        index: Waveform index among same wave_type.

    Returns:
        Mapped x values in display units (μs or ms).
    """
    key = f"{wave_type}{index + 1}" if wave_type == "行波" else wave_type
    target_min, target_max = AXIS_RANGES[key]["x"]
    raw_min, raw_max = float(raw_x.min()), float(raw_x.max())
    if raw_max == raw_min:
        return np.full_like(raw_x, target_min)
    return target_min + (raw_x - raw_min) * (target_max - target_min) / (raw_max - raw_min)


def _downsample(raw_x: np.ndarray, raw_y: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Downsample waveform to at most max_points.

    Args:
        raw_x: Raw x values.
        raw_y: Raw y values.
        max_points: Maximum number of points to keep.

    Returns:
        Downsampled x and y arrays.
    """
    if len(raw_x) <= max_points:
        return raw_x, raw_y
    step = max(1, int(np.ceil(len(raw_x) / max_points)))
    indices = np.arange(0, len(raw_x), step)
    if indices[-1] != len(raw_x) - 1:
        indices = np.append(indices, len(raw_x) - 1)
    return raw_x[indices], raw_y[indices]


def plot_single_waveform(
    waveform: dict[str, Any],
    wave_type: str,
    index: int,
) -> bytes:
    """Plot a single waveform as a 600x280 PNG.

    Args:
        waveform: Dict with "items" list of {"x": float, "y": float}.
        wave_type: "行波" or "工频".
        index: Index among waveforms of the same type.

    Returns:
        PNG image bytes.
    """
    items = waveform.get("items", [])
    if not items:
        raise ValueError("Waveform items are empty")

    raw_x = np.array([p["x"] for p in items], dtype=float)
    raw_y = np.array([p["y"] for p in items], dtype=float)

    key = f"{wave_type}{index + 1}" if wave_type == "行波" else wave_type
    x_range = AXIS_RANGES[key]["x"]
    y_range = AXIS_RANGES[key]["y"]

    # Map raw x to the fixed display range.
    x_values = _map_x(raw_x, wave_type, index)
    # Downsample based on image width (each pixel at most one point).
    x_values, y_values = _downsample(x_values, raw_y, WAVE_IMAGE_WIDTH)

    # Create figure with exact pixel dimensions.
    dpi = 100
    fig_width = WAVE_IMAGE_WIDTH / dpi
    fig_height = WAVE_IMAGE_HEIGHT / dpi
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Grid lines.
    y_ticks = Y_TICKS[key]
    x_ticks = X_TICKS["工频"] if wave_type == "工频" else X_TICKS["行波"]
    for y_val in y_ticks:
        ax.axhline(y_val, color=COLORS["grid"], linewidth=0.8, zorder=1)
    for x_val in x_ticks:
        ax.axvline(x_val, color=COLORS["grid"], linewidth=0.8, zorder=1)

    # Waveform line.
    ax.plot(
        x_values,
        y_values,
        color=COLORS["wave_line"],
        linewidth=1.5,
        zorder=2,
    )

    # Fixed axis limits.
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)

    # Axis styling.
    ax.spines["bottom"].set_color(COLORS["axis"])
    ax.spines["left"].set_color(COLORS["axis"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.spines["left"].set_linewidth(1.5)

    # Ticks.
    ax.set_xticks(x_ticks)
    ax.set_yticks(y_ticks)
    ax.tick_params(axis="both", colors=COLORS["tick_label"], labelsize=FONT_SIZES["tick"])

    # Labels.
    x_unit = "毫秒" if wave_type == "工频" else "微秒"
    ax.set_xlabel(f"时间（{x_unit}）", fontsize=FONT_SIZES["label"], color=COLORS["label"])
    ax.set_ylabel("电流（安培）", fontsize=FONT_SIZES["label"], color=COLORS["label"])

    # Title.
    title_suffix = ""
    if wave_type == "行波":
        title_suffix = f" {index + 1}"
    ax.set_title(
        f"故障波形：{wave_type}波形{title_suffix}",
        fontsize=FONT_SIZES["title"],
        color=COLORS["axis"],
    )

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def plot_waveforms(ripple: TripRippleResponse) -> list[bytes]:
    """Plot all waveforms from a getTripRipple response.

    Args:
        ripple: Parsed getTripRipple response.

    Returns:
        List of PNG bytes in waveform order.
    """
    images: list[bytes] = []
    type_counters: dict[str, int] = {}

    for waveform in ripple.waveforms:
        wave_type = waveform.wave_type
        idx = type_counters.get(wave_type, 0)
        # The raw model already stores items as dicts.
        raw_waveform = {"items": waveform.items}
        images.append(plot_single_waveform(raw_waveform, wave_type, idx))
        type_counters[wave_type] = idx + 1

    return images
