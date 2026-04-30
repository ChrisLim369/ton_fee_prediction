#!/usr/bin/env python3
"""Generate lightweight SVG/PNG charts for the TON fee prediction project.

The script intentionally uses only pandas plus the Python standard library so
the dashboard can be regenerated in the current project environment without
extra plotting dependencies.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"

BLUE = "#2563eb"
GREEN = "#059669"
AMBER = "#d97706"
RED = "#dc2626"
PURPLE = "#7c3aed"
SLATE = "#334155"
GRID = "#e2e8f0"
TEXT = "#0f172a"
MUTED = "#64748b"
BG = "#f8fafc"
CARD = "#ffffff"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def fmt_number(value: float) -> str:
    if value is None or pd.isna(value):
        return ""
    value = float(value)
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.0f}K"
    if abs_value >= 10:
        return f"{value:.0f}"
    return f"{value:.2f}"


def safe_values(values: Iterable[float]) -> list[float]:
    return [float(v) for v in values if v is not None and not pd.isna(v) and math.isfinite(float(v))]


def scale(value: float, min_value: float, max_value: float, low: float, high: float) -> float:
    if max_value == min_value:
        return (low + high) / 2
    return low + (value - min_value) * (high - low) / (max_value - min_value)


def svg_header(width: int, height: int, title: str, subtitle: str = "") -> list[str]:
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="34" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="{TEXT}">{html.escape(title)}</text>',
    ]
    if subtitle:
        lines.append(
            f'<text x="28" y="56" font-family="Arial, sans-serif" font-size="12" fill="{MUTED}">{html.escape(subtitle)}</text>'
        )
    return lines


def svg_footer(lines: list[str], source: str, width: int, height: int) -> None:
    lines.append(
        f'<text x="28" y="{height - 16}" font-family="Arial, sans-serif" font-size="11" fill="{MUTED}">{html.escape(source)}</text>'
    )
    lines.append("</svg>")


def draw_axes(
    lines: list[str],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    min_y: float,
    max_y: float,
    y_label: str,
    x_labels: list[tuple[float, str]] | None = None,
) -> None:
    for i in range(5):
        y = scale(i, 0, 4, y1, y0)
        value = scale(i, 0, 4, min_y, max_y)
        lines.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        lines.append(
            f'<text x="{x0 - 8}" y="{y + 4:.1f}" font-family="Arial, sans-serif" font-size="10" text-anchor="end" fill="{MUTED}">{fmt_number(value)}</text>'
        )
    lines.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{SLATE}" stroke-width="1"/>')
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{SLATE}" stroke-width="1"/>')
    lines.append(
        f'<text x="{x0}" y="{y0 - 10}" font-family="Arial, sans-serif" font-size="11" fill="{MUTED}">{html.escape(y_label)}</text>'
    )
    if x_labels:
        for x, label in x_labels:
            lines.append(f'<line x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y1 + 4}" stroke="{SLATE}" stroke-width="1"/>')
            lines.append(
                f'<text x="{x:.1f}" y="{y1 + 18}" font-family="Arial, sans-serif" font-size="10" text-anchor="middle" fill="{MUTED}">{html.escape(label)}</text>'
            )


def draw_legend(lines: list[str], items: list[tuple[str, str]], x: int, y: int) -> None:
    cursor = x
    for label, color in items:
        lines.append(f'<line x1="{cursor}" y1="{y}" x2="{cursor + 18}" y2="{y}" stroke="{color}" stroke-width="3"/>')
        lines.append(
            f'<text x="{cursor + 24}" y="{y + 4}" font-family="Arial, sans-serif" font-size="11" fill="{TEXT}">{html.escape(label)}</text>'
        )
        cursor += 24 + len(label) * 7 + 30


def line_chart(
    path: Path,
    title: str,
    subtitle: str,
    series: list[tuple[str, pd.Series, str]],
    y_label: str,
    source: str,
    width: int = 980,
    height: int = 420,
    min_y: float | None = None,
    max_y: float | None = None,
) -> None:
    lines = svg_header(width, height, title, subtitle)
    x0, y0, x1, y1 = 76, 82, width - 34, height - 58
    n = max(len(s) for _, s, _ in series)
    values = []
    for _, values_series, _ in series:
        values.extend(safe_values(values_series))
    computed_min = min(values) if values else 0.0
    computed_max = max(values) if values else 1.0
    min_y = computed_min if min_y is None else min_y
    max_y = computed_max if max_y is None else max_y
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    pad = (max_y - min_y) * 0.04
    min_y -= pad
    max_y += pad

    x_labels = []
    if n > 1:
        for idx in [0, n // 2, n - 1]:
            x_labels.append((scale(idx, 0, n - 1, x0, x1), str(idx)))
    draw_axes(lines, x0, y0, x1, y1, min_y, max_y, y_label, x_labels)

    for label, values_series, color in series:
        points = []
        for idx, value in enumerate(values_series):
            if pd.isna(value):
                continue
            x = scale(idx, 0, n - 1, x0, x1)
            y = scale(float(value), min_y, max_y, y1, y0)
            points.append(f"{x:.1f},{y:.1f}")
        if points:
            lines.append(
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
            )
    draw_legend(lines, [(label, color) for label, _, color in series], x0, 70)
    svg_footer(lines, source, width, height)
    path.write_text("\n".join(lines), encoding="utf-8")


def bar_chart(
    path: Path,
    title: str,
    subtitle: str,
    labels: list[str],
    values: list[float],
    colors: list[str],
    y_label: str,
    source: str,
    width: int = 980,
    height: int = 430,
    zero_line: bool = False,
) -> None:
    lines = svg_header(width, height, title, subtitle)
    x0, y0, x1, y1 = 86, 84, width - 34, height - 88
    min_y = min(values + ([0] if zero_line else []))
    max_y = max(values + ([0] if zero_line else []))
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    pad = (max_y - min_y) * 0.08
    min_y -= pad
    max_y += pad
    draw_axes(lines, x0, y0, x1, y1, min_y, max_y, y_label)
    if zero_line:
        zy = scale(0, min_y, max_y, y1, y0)
        lines.append(f'<line x1="{x0}" y1="{zy:.1f}" x2="{x1}" y2="{zy:.1f}" stroke="{SLATE}" stroke-width="1.2"/>')
    gap = 14
    bar_width = max(12, (x1 - x0 - gap * (len(values) + 1)) / max(len(values), 1))
    base_y = scale(0, min_y, max_y, y1, y0) if zero_line else y1
    for idx, (label, value, color) in enumerate(zip(labels, values, colors)):
        x = x0 + gap + idx * (bar_width + gap)
        y = scale(value, min_y, max_y, y1, y0)
        rect_y = min(y, base_y)
        rect_h = abs(base_y - y)
        lines.append(f'<rect x="{x:.1f}" y="{rect_y:.1f}" width="{bar_width:.1f}" height="{rect_h:.1f}" fill="{color}" rx="3"/>')
        lines.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{rect_y - 6:.1f}" font-family="Arial, sans-serif" font-size="10" text-anchor="middle" fill="{TEXT}">{fmt_number(value)}</text>'
        )
        lines.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{y1 + 18}" font-family="Arial, sans-serif" font-size="10" text-anchor="middle" fill="{MUTED}" transform="rotate(22 {x + bar_width / 2:.1f},{y1 + 18})">{html.escape(label[:28])}</text>'
        )
    svg_footer(lines, source, width, height)
    path.write_text("\n".join(lines), encoding="utf-8")


def histogram_svg(
    path: Path,
    fees: pd.Series,
    title: str = "Transaction fee distribution",
    subtitle: str = "Histogram of log10(total_fees), zero-fee transactions excluded",
    source: str = "Source: raw_transactions.csv",
) -> None:
    positive = fees[fees > 0].dropna()
    if positive.empty:
        path.write_text("\n".join(svg_header(980, 430, title, "No positive fee values available")) + "\n</svg>\n")
        return
    log_values = positive.map(lambda v: math.log10(float(v)))
    bins = 28
    min_v, max_v = float(log_values.min()), float(log_values.max())
    width = (max_v - min_v) / bins
    counts = [0] * bins
    for value in log_values:
        idx = min(bins - 1, max(0, int((float(value) - min_v) / width)))
        counts[idx] += 1
    labels = [f"1e{min_v + (i + 0.5) * width:.1f}" for i in range(bins)]
    bar_chart(
        path,
        title,
        subtitle,
        labels,
        counts,
        [BLUE] * bins,
        "transactions",
        source,
        width=980,
        height=430,
    )


def forecast_chart(path: Path, hourly: pd.DataFrame, pred: pd.DataFrame) -> None:
    recent = hourly.tail(96)[["hour", "avg_total_fee"]].copy()
    forecast = pred[["forecast_hour", "predicted_avg_total_fee"]].copy()
    actual_values = list(recent["avg_total_fee"]) + [math.nan] * len(forecast)
    forecast_values = [math.nan] * len(recent) + list(forecast["predicted_avg_total_fee"])
    line_chart(
        path,
        "Recent actual fees and 24-hour forecast",
        "Last 96 actual hours followed by generated forecast",
        [
            ("actual avg fee", pd.Series(actual_values), BLUE),
            ("forecast avg fee", pd.Series(forecast_values), AMBER),
        ],
        "nanoton",
        "Source: hourly_features.csv, predictions.csv",
        width=980,
        height=420,
    )


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    draw.text(xy, text, font=font, fill=hex_to_rgb(fill))


def format_ton(value: float) -> str:
    return f"{value / 1_000_000_000:.6f} TON"


def format_short_hour(value: object) -> str:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return str(value)
    return timestamp.strftime("%m-%d %H:%M UTC")


def forecast_png_chart(path: Path, pred: pd.DataFrame) -> None:
    forecast = pred.copy()
    forecast["horizon_hours"] = pd.to_numeric(forecast["horizon_hours"], errors="coerce")
    forecast["predicted_avg_total_fee"] = pd.to_numeric(forecast["predicted_avg_total_fee"], errors="coerce")
    forecast = forecast.dropna(subset=["horizon_hours", "predicted_avg_total_fee"]).sort_values("horizon_hours").head(24)
    if forecast.empty:
        return

    width, height = 1200, 720
    image = Image.new("RGB", (width, height), hex_to_rgb(BG))
    draw = ImageDraw.Draw(image)

    title_font = load_font(38, bold=True)
    heading_font = load_font(24, bold=True)
    body_font = load_font(21)
    small_font = load_font(17)
    label_font = load_font(15)

    draw.rounded_rectangle((36, 30, width - 36, height - 30), radius=26, fill=hex_to_rgb(CARD), outline=hex_to_rgb(GRID), width=2)
    draw_text(draw, (70, 64), "TON Fee Forecast", title_font, TEXT)

    generated = forecast.iloc[0].get("forecast_generated_at", "")
    generated_label = format_short_hour(generated) if generated else "n/a"
    draw_text(draw, (72, 110), f"Next 24 hours | Generated {generated_label}", body_font, MUTED)

    values = [float(value) for value in forecast["predicted_avg_total_fee"]]
    min_value = min(values)
    max_value = max(values)
    span = max_value - min_value or 1.0
    pad = span * 0.16
    y_min = min_value - pad
    y_max = max_value + pad

    cheapest_index = values.index(min_value)
    highest_index = values.index(max_value)
    cheapest_row = forecast.iloc[cheapest_index]
    highest_row = forecast.iloc[highest_index]
    difference = max_value - min_value
    percent = difference / max_value * 100 if max_value else 0.0

    summary_x = 760
    draw.rounded_rectangle((summary_x, 64, 1128, 206), radius=18, fill=hex_to_rgb("#ecfdf5"), outline=hex_to_rgb("#bbf7d0"), width=2)
    draw_text(draw, (summary_x + 24, 88), "Cheapest window", heading_font, GREEN)
    draw_text(draw, (summary_x + 24, 124), format_short_hour(cheapest_row["forecast_hour"]), body_font, TEXT)
    draw_text(draw, (summary_x + 24, 158), f"{format_ton(min_value)} | {percent:.1f}% below peak", body_font, TEXT)

    plot_left, plot_top, plot_right, plot_bottom = 90, 250, 1110, 570
    draw.rounded_rectangle((plot_left - 18, plot_top - 28, plot_right + 18, plot_bottom + 48), radius=18, fill=hex_to_rgb("#ffffff"), outline=hex_to_rgb(GRID), width=1)

    for idx in range(5):
        y = plot_bottom - idx * (plot_bottom - plot_top) / 4
        value = y_min + idx * (y_max - y_min) / 4
        draw.line((plot_left, y, plot_right, y), fill=hex_to_rgb(GRID), width=1)
        draw_text(draw, (plot_left - 78, int(y) - 10), format_ton(value).replace(" TON", ""), label_font, MUTED)

    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=hex_to_rgb(SLATE), width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=hex_to_rgb(SLATE), width=2)

    def point(index: int, value: float) -> tuple[float, float]:
        x = plot_left + index * (plot_right - plot_left) / max(len(values) - 1, 1)
        y = plot_bottom - (value - y_min) * (plot_bottom - plot_top) / (y_max - y_min)
        return x, y

    points = [point(index, value) for index, value in enumerate(values)]
    for left, right in zip(points, points[1:]):
        draw.line((*left, *right), fill=hex_to_rgb(BLUE), width=5)

    for index, (x, y) in enumerate(points):
        color = GREEN if index == cheapest_index else RED if index == highest_index else BLUE
        radius = 9 if index in {cheapest_index, highest_index} else 5
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=hex_to_rgb(color), outline=hex_to_rgb(CARD), width=3)

    for index in [0, 5, 11, 17, 23]:
        if index >= len(points):
            continue
        x, _ = points[index]
        label = f"h{int(forecast.iloc[index]['horizon_hours']):02d}"
        draw_text(draw, (int(x) - 14, plot_bottom + 18), label, label_font, MUTED)

    cheapest_x, cheapest_y = points[cheapest_index]
    highest_x, highest_y = points[highest_index]
    draw_text(draw, (int(cheapest_x) + 14, int(cheapest_y) - 26), "lowest", small_font, GREEN)
    draw_text(draw, (int(highest_x) + 14, int(highest_y) - 26), "highest", small_font, RED)

    draw_text(draw, (90, 620), f"Range: {format_ton(min_value)} - {format_ton(max_value)}", body_font, TEXT)
    draw_text(draw, (90, 652), "Directional estimate only. Actual fees can change quickly with network activity.", small_font, MUTED)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)

    hourly = pd.read_csv(ROOT / "hourly_features.csv")
    comparison = pd.read_csv(ROOT / "models" / "model_comparison.csv")
    rolling_backtest_path = ROOT / "models" / "rolling_backtest.csv"
    rolling_backtest = (
        pd.read_csv(rolling_backtest_path)
        if rolling_backtest_path.exists()
        else pd.DataFrame()
    )
    actual_vs_predicted = pd.read_csv(ROOT / "actual_vs_predicted.csv")
    predictions = pd.read_csv(ROOT / "predictions.csv")
    raw_path = ROOT / "raw_transactions.csv"

    line_chart(
        FIGURES / "hourly_fee_trend.svg",
        "Hourly fee trend",
        "Average, median, and p90 total fee by hour",
        [
            ("avg fee", hourly["avg_total_fee"], BLUE),
            ("median fee", hourly["median_total_fee"], GREEN),
            ("p90 fee", hourly["p90_total_fee"], AMBER),
        ],
        "nanoton",
        "Source: hourly_features.csv",
    )

    line_chart(
        FIGURES / "network_activity_trend.svg",
        "Network activity sample trend",
        "Hourly transaction sample count and unique account sample count",
        [
            ("tx count", hourly["tx_count"], BLUE),
            ("unique accounts", hourly["unique_accounts"], PURPLE),
        ],
        "count",
        "Source: hourly_features.csv; capped windows are sample counts",
    )

    line_chart(
        FIGURES / "actual_vs_predicted.svg",
        "Holdout actual vs predicted",
        "Chronological test split for the selected best model",
        [
            ("actual", actual_vs_predicted["actual_next_hour_avg_fee"], BLUE),
            ("predicted", actual_vs_predicted["predicted_next_hour_avg_fee"], RED),
        ],
        "nanoton",
        "Source: actual_vs_predicted.csv",
    )

    forecast_chart(FIGURES / "forecast_next_24h.svg", hourly, predictions)
    forecast_png_chart(FIGURES / "forecast_next_24h.png", predictions)
    if raw_path.exists():
        raw_fees = pd.read_csv(raw_path, usecols=["total_fees"])["total_fees"]
        histogram_svg(FIGURES / "fee_distribution.svg", raw_fees)
        fee_distribution_source = "raw_transactions.csv"
        fee_distribution_rows = int(len(raw_fees))
    else:
        histogram_svg(
            FIGURES / "fee_distribution.svg",
            hourly["avg_total_fee"],
            title="Hourly average fee distribution",
            subtitle="Histogram of log10(hourly avg_total_fee); raw transaction CSV unavailable in CI",
            source="Source: hourly_features.csv",
        )
        fee_distribution_source = "hourly_features.csv"
        fee_distribution_rows = int(len(hourly))

    top_models = comparison.head(8).copy()
    bar_chart(
        FIGURES / "model_r2_comparison.svg",
        "Model R2 comparison",
        "Higher is better; chronological holdout split",
        list(top_models["model_name"]),
        [float(v) for v in top_models["r2"]],
        [GREEN if v >= 0 else RED for v in top_models["r2"]],
        "R2",
        "Source: models/model_comparison.csv",
        zero_line=True,
    )

    bar_chart(
        FIGURES / "model_mae_comparison.svg",
        "Model MAE comparison",
        "Lower is better; chronological holdout split",
        list(top_models["model_name"]),
        [float(v) for v in top_models["mae"]],
        [BLUE] * len(top_models),
        "nanoton",
        "Source: models/model_comparison.csv",
    )

    if not rolling_backtest.empty:
        top_rolling = rolling_backtest.head(8).copy()
        bar_chart(
            FIGURES / "rolling_backtest_r2_comparison.svg",
            "Rolling backtest mean R2",
            "Recent 24-hour expanding-window folds; higher is better",
            list(top_rolling["model_name"]),
            [float(v) for v in top_rolling["mean_r2"]],
            [GREEN if v >= 0 else RED for v in top_rolling["mean_r2"]],
            "mean R2",
            "Source: models/rolling_backtest.csv",
            zero_line=True,
        )

    print(
        {
            "figures": str(FIGURES),
            "charts": sorted(path.name for path in FIGURES.glob("*.svg")),
            "hourly_rows": int(len(hourly)),
            "fee_distribution_source": fee_distribution_source,
            "fee_distribution_rows": fee_distribution_rows,
            "best_model": str(comparison.iloc[0]["model_name"]),
            "best_r2": float(comparison.iloc[0]["r2"]),
        }
    )


if __name__ == "__main__":
    main()
