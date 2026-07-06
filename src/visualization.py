from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from .common import FIGURES_DIR

def svg_text(x: float, y: float, text: str, size: int = 12, anchor: str = "start", weight: str = "400", color: str = "#2B2B2B") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{html.escape(str(text))}</text>'

def save_bar_svg(path: Path, title: str, labels: list[str], values: list[float], y_label: str, color: str = "#2F5F8F", value_suffix: str = "") -> None:
    width, height = 960, 560
    margin = {"left": 90, "right": 40, "top": 80, "bottom": 140}
    chart_w = width - margin["left"] - margin["right"]
    chart_h = height - margin["top"] - margin["bottom"]
    max_value = max(values) if values else 1
    max_value = max_value if max_value > 0 else 1
    gap = 18
    bar_w = (chart_w - gap * (len(values) - 1)) / max(len(values), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F8FA"/>',
        svg_text(width / 2, 38, title, 22, "middle", "700"),
        svg_text(24, margin["top"] + chart_h / 2, y_label, 12, "middle", "600"),
        f'<line x1="{margin["left"]}" y1="{margin["top"] + chart_h}" x2="{margin["left"] + chart_w}" y2="{margin["top"] + chart_h}" stroke="#BBBBBB"/>',
        f'<line x1="{margin["left"]}" y1="{margin["top"]}" x2="{margin["left"]}" y2="{margin["top"] + chart_h}" stroke="#BBBBBB"/>',
    ]
    for i, (label, value) in enumerate(zip(labels, values)):
        x = margin["left"] + i * (bar_w + gap)
        h = chart_h * value / max_value
        y = margin["top"] + chart_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>')
        parts.append(svg_text(x + bar_w / 2, y - 8, f"{value:,.1f}{value_suffix}", 11, "middle", "600"))
        short = label if len(label) <= 18 else label[:16] + "..."
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{margin["top"] + chart_h + 24:.1f}" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#2B2B2B" text-anchor="end" transform="rotate(-35 {x + bar_w / 2:.1f},{margin["top"] + chart_h + 24:.1f})">{html.escape(short)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

def save_horizontal_bar_svg(path: Path, title: str, labels: list[str], values: list[float], x_label: str, color: str = "#B23A48", value_suffix: str = "") -> None:
    width, height = 1080, max(520, 110 + len(values) * 34)
    left, right, top, bottom = 320, 60, 75, 55
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_value = max(values) if values else 1
    max_value = max_value if max_value > 0 else 1
    row_h = chart_h / max(len(values), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F8FA"/>',
        svg_text(width / 2, 36, title, 22, "middle", "700"),
        f'<line x1="{left}" y1="{top + chart_h}" x2="{left + chart_w}" y2="{top + chart_h}" stroke="#BBBBBB"/>',
        svg_text(left + chart_w / 2, height - 18, x_label, 12, "middle", "600"),
    ]
    for i, (label, value) in enumerate(zip(labels, values)):
        y = top + i * row_h + 5
        h = max(row_h - 10, 14)
        w = chart_w * value / max_value
        short = label if len(label) <= 42 else label[:40] + "..."
        parts.append(svg_text(left - 12, y + h * 0.68, short, 11, "end"))
        parts.append(f'<rect x="{left}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>')
        parts.append(svg_text(left + w + 8, y + h * 0.68, f"{value:,.1f}{value_suffix}", 11, "start", "600"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

def save_line_svg(path: Path, title: str, labels: list[str], series: dict[str, list[float]], y_label: str) -> None:
    width, height = 1160, 560
    left, right, top, bottom = 80, 160, 75, 120
    chart_w = width - left - right
    chart_h = height - top - bottom
    all_values = [value for values in series.values() for value in values]
    min_value = min(all_values) if all_values else 0
    max_value = max(all_values) if all_values else 1
    if max_value == min_value:
        max_value += 1
    colors = ["#2F5F8F", "#B23A48", "#2E7D32"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F8FA"/>',
        svg_text(width / 2, 36, title, 22, "middle", "700"),
        f'<line x1="{left}" y1="{top + chart_h}" x2="{left + chart_w}" y2="{top + chart_h}" stroke="#BBBBBB"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_h}" stroke="#BBBBBB"/>',
        svg_text(22, top + chart_h / 2, y_label, 12, "middle", "600"),
    ]
    x_step = chart_w / max(len(labels) - 1, 1)
    for idx, (name, values) in enumerate(series.items()):
        color = colors[idx % len(colors)]
        points = []
        for i, value in enumerate(values):
            x = left + i * x_step
            y = top + chart_h - ((value - min_value) / (max_value - min_value)) * chart_h
            points.append(f"{x:.1f},{y:.1f}")
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        parts.append(f'<rect x="{width - 135}" y="{top + idx * 24}" width="12" height="12" fill="{color}"/>')
        parts.append(svg_text(width - 116, top + 11 + idx * 24, name, 12, "start"))
    for i, label in enumerate(labels):
        if i % max(1, len(labels) // 14) == 0:
            x = left + i * x_step
            parts.append(f'<text x="{x:.1f}" y="{top + chart_h + 26}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#2B2B2B" text-anchor="end" transform="rotate(-45 {x:.1f},{top + chart_h + 26})">{html.escape(label)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

def save_figures(df: pd.DataFrame, orders: pd.DataFrame) -> dict[str, Path]:
    figures = {}
    shipping = (
        orders.groupby("shipping_mode")
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay=("shipping_delay_days", "mean"))
        .sort_values("late_delivery_rate", ascending=False)
    )
    path = FIGURES_DIR / "late_delivery_rate_by_shipping_mode.svg"
    save_bar_svg(path, "Late Delivery Rate by Shipping Mode", shipping.index.astype(str).tolist(), (shipping["late_delivery_rate"] * 100).tolist(), "Late delivery rate (%)", "#B23A48", "%")
    figures["shipping_mode"] = path

    market = (
        orders.groupby("market")
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"))
        .sort_values("total_orders", ascending=False)
    )
    path = FIGURES_DIR / "market_order_volume.svg"
    save_bar_svg(path, "Order Volume by Market", market.index.astype(str).tolist(), market["total_orders"].tolist(), "Total orders", "#2F5F8F")
    figures["market"] = path

    monthly = (
        orders.groupby("order_year_month")
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), total_sales=("net_order_sales", "sum"))
        .reset_index()
        .sort_values("order_year_month")
    )
    path = FIGURES_DIR / "monthly_sales_late_delivery_trend.svg"
    save_line_svg(
        path,
        "Monthly Sales and Late Delivery Rate",
        monthly["order_year_month"].tolist(),
        {"Sales ($M)": (monthly["total_sales"] / 1_000_000).tolist(), "Late rate (%)": (monthly["late_delivery_rate"] * 100).tolist()},
        "Scaled values",
    )
    figures["monthly"] = path

    category = (
        df.groupby("category_name")
        .agg(total_sales=("order_item_total", "sum"), total_profit=("benefit_per_order", "sum"), order_items=("order_item_id", "count"))
        .sort_values("total_sales", ascending=False)
        .head(10)
        .sort_values("total_sales")
    )
    path = FIGURES_DIR / "top_categories_sales.svg"
    save_horizontal_bar_svg(path, "Top Categories by Net Sales", category.index.astype(str).tolist(), (category["total_sales"] / 1_000_000).tolist(), "Net sales ($M)", "#2F5F8F", "M")
    figures["category"] = path

    delay = orders["shipping_delay_days"].value_counts().sort_index()
    path = FIGURES_DIR / "shipping_delay_distribution.svg"
    save_bar_svg(path, "Distribution of Shipping Delay Days", delay.index.astype(str).tolist(), delay.values.tolist(), "Orders", "#5C4B8A")
    figures["delay_distribution"] = path

    region = (
        orders.groupby(["market", "order_region"])
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay=("shipping_delay_days", "mean"), total_sales=("net_order_sales", "sum"))
        .query("total_orders >= 500")
        .sort_values(["late_delivery_rate", "total_orders"], ascending=[False, False])
        .head(12)
    )
    labels = [f"{idx[0]} / {idx[1]}" for idx in region.index]
    path = FIGURES_DIR / "high_volume_regions_late_delivery.svg"
    save_horizontal_bar_svg(path, "High-Volume Regions with Highest Late Delivery Rates", labels[::-1], (region["late_delivery_rate"].iloc[::-1] * 100).tolist(), "Late delivery rate (%)", "#B23A48", "%")
    figures["region"] = path
    return figures
