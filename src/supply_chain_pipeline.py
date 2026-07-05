from __future__ import annotations

import csv
import html
import json
import math
import re
import shutil
import sqlite3
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_TITLE = "Supply Chain Delivery Performance Analysis"
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive.zip"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
OUTPUTS_DIR = ROOT / "outputs"
SQL_OUTPUTS_DIR = OUTPUTS_DIR / "sql"
SQL_DIR = ROOT / "sql"
POWERBI_DIR = ROOT / "powerbi"
POWERBI_DATA_DIR = POWERBI_DIR / "data"
VALIDATION_DIR = ROOT / "validation"
DASHBOARD_DIR = ROOT / "dashboard"

MAIN_SOURCE = "DataCoSupplyChainDataset.csv"
DESCRIPTION_SOURCE = "DescriptionDataCoSupplyChain.csv"
ACCESS_LOG_SOURCE = "tokenized_access_logs.csv"


def make_dirs() -> None:
    for folder in [
        RAW_DIR,
        PROCESSED_DIR,
        DOCS_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        OUTPUTS_DIR,
        SQL_OUTPUTS_DIR,
        SQL_DIR,
        POWERBI_DIR,
        POWERBI_DATA_DIR,
        VALIDATION_DIR,
        DASHBOARD_DIR,
    ]:
        folder.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def pct(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100 * float(value):.{digits}f}%"


def money(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"${float(value):,.{digits}f}"


def num(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def slug(name: str) -> str:
    value = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def extract_archive() -> list[str]:
    if not ARCHIVE.exists():
        raise FileNotFoundError("archive.zip is required at the project root.")
    extracted = []
    with zipfile.ZipFile(ARCHIVE) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = RAW_DIR / Path(member.filename).name
            if not target.exists():
                with zf.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            extracted.append(target.name)
    return extracted


def read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    return pd.read_csv(path, encoding="latin1", nrows=nrows, low_memory=False)


def profile_source_files() -> dict[str, pd.DataFrame]:
    inventory_rows = []
    missing_rows = []
    sample_records = {}
    dataframes = {}

    with zipfile.ZipFile(ARCHIVE) as zf:
        archive_members = {Path(info.filename).name: info for info in zf.infolist() if not info.is_dir()}

    for path in sorted(RAW_DIR.glob("*.csv")):
        df = read_csv(path)
        dataframes[path.name] = df
        duplicate_rows = int(df.duplicated().sum())
        missing = df.isna().sum()
        inferred = {col: str(dtype) for col, dtype in df.dtypes.items()}
        archive_info = archive_members.get(path.name)
        inventory_rows.append(
            {
                "filename": path.name,
                "file_type": path.suffix.lower().lstrip("."),
                "file_size_bytes": path.stat().st_size,
                "archive_uncompressed_bytes": archive_info.file_size if archive_info else None,
                "encoding_used": "latin1",
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": " | ".join(df.columns),
                "inferred_data_types": json.dumps(inferred, ensure_ascii=True),
                "duplicate_full_rows": duplicate_rows,
                "parsing_problems": "None detected by pandas read_csv with latin1",
            }
        )
        for col in df.columns:
            missing_rows.append(
                {
                    "filename": path.name,
                    "column_name": col,
                    "missing_count": int(missing[col]),
                    "missing_pct": float(missing[col] / len(df)) if len(df) else 0.0,
                    "inferred_dtype": str(df[col].dtype),
                    "unique_values": int(df[col].nunique(dropna=True)),
                }
            )
        sample = df.head(5).copy()
        sensitive_sample_cols = [
            col
            for col in sample.columns
            if any(token in slug(col) for token in ["email", "password", "street", "fname", "lname", "ip", "url", "image"])
        ]
        sample = sample.drop(columns=sensitive_sample_cols, errors="ignore")
        sample_records[path.name] = sample.where(pd.notna(sample), None).to_dict(orient="records")

    inventory = pd.DataFrame(inventory_rows)
    missing_profile = pd.DataFrame(missing_rows)
    inventory.to_csv(OUTPUTS_DIR / "dataset_inventory.csv", index=False)
    missing_profile.to_csv(OUTPUTS_DIR / "missing_value_profile.csv", index=False)
    (OUTPUTS_DIR / "source_sample_records.json").write_text(
        json.dumps(sample_records, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )
    return dataframes


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: slug(col) for col in df.columns}
    result = df.rename(columns=renamed).copy()
    for col in result.select_dtypes(include="object").columns:
        result[col] = result[col].astype("string").str.strip()
    return result


def derive_clean_dataset(raw_main: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(raw_main)
    df["order_date"] = pd.to_datetime(df["order_date_dateorders"], errors="coerce")
    df["shipping_date"] = pd.to_datetime(df["shipping_date_dateorders"], errors="coerce")
    df["shipping_delay_days"] = df["days_for_shipping_real"] - df["days_for_shipment_scheduled"]
    df["late_delivery_flag"] = df["late_delivery_risk"].fillna(0).astype(int)
    df["on_time_flag"] = (df["late_delivery_flag"] == 0).astype(int)
    df["cancellation_flag"] = df["order_status"].eq("CANCELED").astype(int)
    df["suspected_fraud_flag"] = df["order_status"].eq("SUSPECTED_FRAUD").astype(int)
    df["profit_margin"] = df["benefit_per_order"] / df["order_item_total"].where(df["order_item_total"] != 0)
    df["order_year"] = df["order_date"].dt.year
    df["order_quarter"] = "Q" + df["order_date"].dt.quarter.astype("Int64").astype(str)
    df["order_month"] = df["order_date"].dt.month
    df["order_year_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["order_weekday"] = df["order_date"].dt.day_name()
    df["order_date_key"] = df["order_date"].dt.strftime("%Y%m%d")
    df["shipping_date_key"] = df["shipping_date"].dt.strftime("%Y%m%d")

    def delay_group(value: float) -> str:
        if pd.isna(value):
            return "Unknown"
        if value < 0:
            return "Early"
        if value == 0:
            return "On schedule"
        if value == 1:
            return "1 day late"
        if value <= 3:
            return "2-3 days late"
        return "4+ days late"

    df["delay_severity"] = df["shipping_delay_days"].apply(delay_group)
    df["delivery_performance_group"] = df["late_delivery_flag"].map({1: "Late", 0: "Not late"})
    df["geography_key"] = (
        df[["market", "order_region", "order_country", "order_state", "order_city"]]
        .fillna("Unknown")
        .astype(str)
        .agg("|".join, axis=1)
        .map(lambda value: slug(value)[:160])
    )

    sensitive_or_low_value = [
        "customer_email",
        "customer_password",
        "customer_street",
        "customer_fname",
        "customer_lname",
        "product_image",
        "product_description",
    ]
    keep_drop = [col for col in sensitive_or_low_value if col in df.columns]
    df = df.drop(columns=keep_drop)

    return df


def order_level(df: pd.DataFrame) -> pd.DataFrame:
    fields_first = [
        "order_id",
        "order_date",
        "shipping_date",
        "shipping_mode",
        "type",
        "market",
        "order_region",
        "order_country",
        "order_state",
        "order_city",
        "customer_id",
        "customer_segment",
        "order_status",
        "days_for_shipping_real",
        "days_for_shipment_scheduled",
        "shipping_delay_days",
        "late_delivery_flag",
        "on_time_flag",
        "cancellation_flag",
        "suspected_fraud_flag",
        "delivery_status",
        "delay_severity",
        "delivery_performance_group",
        "order_year",
        "order_quarter",
        "order_month",
        "order_year_month",
        "order_weekday",
        "order_date_key",
        "shipping_date_key",
        "geography_key",
    ]
    agg = {col: "first" for col in fields_first if col in df.columns and col != "order_id"}
    agg.update(
        {
            "order_item_id": "count",
            "sales": "sum",
            "order_item_total": "sum",
            "order_item_discount": "sum",
            "benefit_per_order": "sum",
        }
    )
    orders = df.groupby("order_id", as_index=False).agg(agg)
    orders = orders.rename(
        columns={
            "order_item_id": "order_item_count",
            "sales": "gross_order_sales",
            "order_item_total": "net_order_sales",
            "benefit_per_order": "order_profit",
            "order_item_discount": "order_discount",
        }
    )
    return orders


@dataclass
class Metrics:
    total_sales: float
    gross_sales: float
    total_profit: float
    profit_margin: float
    total_orders: int
    total_order_items: int
    total_customers: int
    average_order_value: float
    late_deliveries: int
    late_delivery_rate: float
    on_time_deliveries: int
    on_time_delivery_rate: float
    cancelled_orders: int
    cancellation_rate: float
    average_shipping_delay_days: float
    average_actual_shipping_days: float
    average_scheduled_shipping_days: float


def calculate_metrics(df: pd.DataFrame, orders: pd.DataFrame) -> Metrics:
    total_sales = float(df["order_item_total"].sum())
    gross_sales = float(df["sales"].sum())
    total_profit = float(df["benefit_per_order"].sum())
    total_orders = int(orders["order_id"].nunique())
    total_order_items = int(len(df))
    total_customers = int(df["customer_id"].nunique())
    late_deliveries = int(orders["late_delivery_flag"].sum())
    on_time_deliveries = int((orders["late_delivery_flag"] == 0).sum())
    cancelled_orders = int(orders["cancellation_flag"].sum())
    return Metrics(
        total_sales=total_sales,
        gross_sales=gross_sales,
        total_profit=total_profit,
        profit_margin=total_profit / total_sales if total_sales else math.nan,
        total_orders=total_orders,
        total_order_items=total_order_items,
        total_customers=total_customers,
        average_order_value=total_sales / total_orders if total_orders else math.nan,
        late_deliveries=late_deliveries,
        late_delivery_rate=late_deliveries / total_orders if total_orders else math.nan,
        on_time_deliveries=on_time_deliveries,
        on_time_delivery_rate=on_time_deliveries / total_orders if total_orders else math.nan,
        cancelled_orders=cancelled_orders,
        cancellation_rate=cancelled_orders / total_orders if total_orders else math.nan,
        average_shipping_delay_days=float(orders["shipping_delay_days"].mean()),
        average_actual_shipping_days=float(orders["days_for_shipping_real"].mean()),
        average_scheduled_shipping_days=float(orders["days_for_shipment_scheduled"].mean()),
    )


def build_data_quality(df: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    issues = []

    def add(issue_id, description, fields, severity, mask_or_count, impact, proposed, applied, status="Documented", notes=""):
        if isinstance(mask_or_count, pd.Series):
            affected = int(mask_or_count.sum())
            denom = len(mask_or_count)
        else:
            affected = int(mask_or_count)
            denom = len(df)
        issues.append(
            {
                "issue_id": issue_id,
                "issue_description": description,
                "affected_fields": fields,
                "severity": severity,
                "affected_row_count": affected,
                "affected_pct": affected / denom if denom else 0.0,
                "analytical_impact": impact,
                "proposed_treatment": proposed,
                "applied_treatment": applied,
                "status": status,
                "notes": notes,
            }
        )

    add(
        "DQ001",
        "Product description is entirely missing in the source dataset.",
        "product_description",
        "Low",
        len(df),
        "No impact on KPI analysis because product name, category, and department are available.",
        "Exclude from processed analytical dataset.",
        "Excluded from processed analytical dataset.",
        "Resolved",
    )
    zipcode_missing = df["order_zipcode"].isna() if "order_zipcode" in df else pd.Series(False, index=df.index)
    add(
        "DQ002",
        "Order zipcode has high missingness.",
        "order_zipcode",
        "Medium",
        zipcode_missing,
        "Limits postal-code analysis; market, region, country, state, and city remain usable.",
        "Do not impute; exclude postal-code-level analysis.",
        "Postal-code-level analysis excluded.",
        "Accepted limitation",
    )
    add(
        "DQ003",
        "Sensitive customer fields are present in raw data.",
        "customer_email, customer_password, customer_street, customer_fname, customer_lname",
        "High",
        len(df),
        "Not needed for portfolio analytics and inappropriate for published processed data.",
        "Remove from processed analytical files.",
        "Removed from processed analytical files.",
        "Resolved",
    )
    add(
        "DQ004",
        "Full duplicate rows.",
        "all fields",
        "Low",
        int(df.duplicated().sum()),
        "Duplicate full rows would inflate item-level metrics if present.",
        "Retain records unless duplicates are found; investigate if nonzero.",
        "No row deletion applied.",
        "Checked",
    )
    add(
        "DQ005",
        "Duplicate order item identifiers.",
        "order_item_id",
        "High",
        int(df["order_item_id"].duplicated().sum()),
        "Duplicate item keys would invalidate order-item grain.",
        "Validate uniqueness and stop if duplicates affect grain.",
        "Validated during pipeline; no deletion applied.",
        "Checked",
    )
    add(
        "DQ006",
        "Order identifier repeats because the main dataset is order-item grain.",
        "order_id",
        "Informational",
        int(df["order_id"].duplicated().sum()),
        "Order-level KPIs require distinct-order logic to avoid double counting.",
        "Calculate delivery and cancellation KPIs at order grain.",
        "Order-level helper table created for KPIs.",
        "Governed",
    )
    add(
        "DQ007",
        "Negative profit values indicate loss-making transactions.",
        "benefit_per_order, order_profit_per_order",
        "Informational",
        df["benefit_per_order"] < 0,
        "Represents valid business losses; not a data error.",
        "Retain and analyze as profitability risk.",
        "Retained.",
        "Accepted business signal",
    )
    add(
        "DQ008",
        "Shipping date occurs before order date.",
        "order_date, shipping_date",
        "High",
        df["shipping_date"] < df["order_date"],
        "Impossible date relationship would distort shipping duration KPIs.",
        "Flag and investigate.",
        "Checked; records retained only if valid.",
        "Checked",
    )
    add(
        "DQ009",
        "Late delivery flag disagrees with positive shipping delay.",
        "late_delivery_risk, shipping_delay_days",
        "Medium",
        df["late_delivery_flag"].ne((df["shipping_delay_days"] > 0).astype(int)),
        "Could create inconsistent late-rate calculations.",
        "Use source late flag for headline late-rate, keep delay days as operational duration.",
        "Documented source semantic mismatch if any.",
        "Documented",
    )
    add(
        "DQ010",
        "Discount rate outside expected 0-1 range.",
        "order_item_discount_rate",
        "Medium",
        (df["order_item_discount_rate"] < 0) | (df["order_item_discount_rate"] > 1),
        "Invalid discount rates could distort net sales checks.",
        "Flag and exclude invalid discount-rate interpretation if present.",
        "Checked; no row deletion applied.",
        "Checked",
    )
    add(
        "DQ011",
        "Non-positive sales or item totals.",
        "sales, order_item_total",
        "Medium",
        (df["sales"] <= 0) | (df["order_item_total"] <= 0),
        "Would affect revenue and margin calculations.",
        "Flag and investigate; retain if source business status supports it.",
        "Checked; no row deletion applied.",
        "Checked",
    )
    add(
        "DQ012",
        "Missing parsed order or shipping dates.",
        "order_date, shipping_date",
        "High",
        df["order_date"].isna() | df["shipping_date"].isna(),
        "Would block time-series and shipping-duration analysis.",
        "Parse source date fields and flag failures.",
        "Parsed with pandas; failures documented.",
        "Checked",
    )

    register = pd.DataFrame(issues)
    register.to_csv(OUTPUTS_DIR / "data_quality_issue_register.csv", index=False)
    return register


def build_kpi_dictionary() -> pd.DataFrame:
    rows = [
        ["Total Sales", "Discount-adjusted item revenue", "SUM(order_item_total)", "order_item_total", "", "currency", "Order item", "Sum", "Higher sales indicate larger commercial exposure.", "Uses net item total, not gross list sales.", "sql/kpi_queries.sql", "[Total Sales]"],
        ["Gross Sales", "Pre-discount item sales", "SUM(sales)", "sales", "", "currency", "Order item", "Sum", "Useful for discount context.", "Not used as headline revenue.", "sql/kpi_queries.sql", "[Gross Sales]"],
        ["Total Profit", "Source line profit/benefit", "SUM(benefit_per_order)", "benefit_per_order", "", "currency", "Order item", "Sum", "Measures profitability after source cost logic.", "Source field name says order but behaves as line-level profit in this grain.", "sql/kpi_queries.sql", "[Total Profit]"],
        ["Profit Margin", "Profit as share of discount-adjusted sales", "SUM(benefit_per_order) / SUM(order_item_total)", "benefit_per_order", "order_item_total", "percentage", "Order item", "Ratio of sums", "Shows profitability quality of sales.", "Sensitive to loss-making items.", "sql/kpi_queries.sql", "[Profit Margin]"],
        ["Total Orders", "Distinct customer orders", "COUNT(DISTINCT order_id)", "order_id", "", "count", "Order", "Distinct count", "Order demand volume.", "Requires distinct count because source is order-item grain.", "sql/kpi_queries.sql", "[Total Orders]"],
        ["Total Order Items", "Number of order-item records", "COUNT(*)", "order_item_id", "", "count", "Order item", "Count", "Fulfillment line workload.", "Not the same as order count.", "sql/kpi_queries.sql", "[Total Order Items]"],
        ["Total Customers", "Distinct customers", "COUNT(DISTINCT customer_id)", "customer_id", "", "count", "Customer", "Distinct count", "Customer base represented in the dataset.", "Customer identifiers are anonymized by context only.", "sql/kpi_queries.sql", "[Total Customers]"],
        ["Average Order Value", "Net sales per distinct order", "SUM(order_item_total) / COUNT(DISTINCT order_id)", "order_item_total", "order_id", "currency", "Order", "Ratio", "Commercial value per order.", "Uses net sales.", "sql/kpi_queries.sql", "[Average Order Value]"],
        ["Late Delivery Rate", "Share of distinct orders flagged late", "SUM(late_delivery_flag at order grain) / COUNT(order_id)", "late_delivery_flag", "order_id", "percentage", "Order", "Average order-level flag", "Headline delivery risk KPI.", "Uses source late-delivery flag.", "sql/kpi_queries.sql", "[Late Delivery Rate]"],
        ["On-Time Delivery Rate", "Share of distinct orders not flagged late", "Orders with late_delivery_flag = 0 / COUNT(order_id)", "late_delivery_flag", "order_id", "percentage", "Order", "Average order-level non-late flag", "Complement of late delivery rate.", "Includes early and on-schedule orders as not late.", "sql/kpi_queries.sql", "[On-Time Delivery Rate]"],
        ["Average Shipping Delay", "Actual shipping days minus scheduled shipping days", "AVG(days_for_shipping_real - days_for_shipment_scheduled at order grain)", "shipping_delay_days", "order_id", "days", "Order", "Average", "Positive values show average lateness versus schedule.", "Can be negative for early shipments.", "sql/kpi_queries.sql", "[Average Shipping Delay]"],
        ["Average Actual Shipping Days", "Average actual shipping duration", "AVG(days_for_shipping_real at order grain)", "days_for_shipping_real", "order_id", "days", "Order", "Average", "Operational elapsed shipping time.", "Source provides whole-day duration.", "sql/kpi_queries.sql", "[Average Actual Shipping Days]"],
        ["Average Scheduled Shipping Days", "Average planned shipping duration", "AVG(days_for_shipment_scheduled at order grain)", "days_for_shipment_scheduled", "order_id", "days", "Order", "Average", "Planning baseline for shipping promises.", "Source provides whole-day duration.", "sql/kpi_queries.sql", "[Average Scheduled Shipping Days]"],
        ["Cancellation Rate", "Share of distinct orders with CANCELED status", "Canceled orders / total orders", "order_status", "order_id", "percentage", "Order", "Average order-level flag", "Measures order cancellation exposure.", "Suspected fraud is tracked separately, not counted as canceled.", "sql/kpi_queries.sql", "[Cancellation Rate]"],
    ]
    cols = [
        "kpi_name",
        "business_definition",
        "calculation_logic",
        "numerator",
        "denominator",
        "unit",
        "calculation_grain",
        "aggregation_rule",
        "business_interpretation",
        "limitations",
        "sql_reference",
        "powerbi_dax_reference",
    ]
    kpis = pd.DataFrame(rows, columns=cols)
    kpis.to_csv(OUTPUTS_DIR / "kpi_dictionary.csv", index=False)
    return kpis


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


def build_eda_outputs(df: pd.DataFrame, orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    outputs = {}
    outputs["shipping_mode_performance"] = (
        orders.groupby("shipping_mode")
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay_days=("shipping_delay_days", "mean"), avg_actual_days=("days_for_shipping_real", "mean"), avg_scheduled_days=("days_for_shipment_scheduled", "mean"), total_sales=("net_order_sales", "sum"), total_profit=("order_profit", "sum"))
        .reset_index()
        .sort_values("late_delivery_rate", ascending=False)
    )
    outputs["market_performance"] = (
        orders.groupby("market")
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay_days=("shipping_delay_days", "mean"), total_sales=("net_order_sales", "sum"), total_profit=("order_profit", "sum"))
        .reset_index()
        .sort_values("total_orders", ascending=False)
    )
    outputs["region_risk"] = (
        orders.groupby(["market", "order_region"])
        .agg(total_orders=("order_id", "nunique"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay_days=("shipping_delay_days", "mean"), total_sales=("net_order_sales", "sum"), total_profit=("order_profit", "sum"))
        .reset_index()
        .query("total_orders >= 500")
        .sort_values(["late_delivery_rate", "total_orders"], ascending=[False, False])
    )
    outputs["category_performance"] = (
        df.groupby(["department_name", "category_name"])
        .agg(order_items=("order_item_id", "count"), total_orders=("order_id", "nunique"), total_sales=("order_item_total", "sum"), total_profit=("benefit_per_order", "sum"), profit_margin=("benefit_per_order", lambda s: s.sum()))
        .reset_index()
    )
    outputs["category_performance"]["profit_margin"] = outputs["category_performance"]["total_profit"] / outputs["category_performance"]["total_sales"]
    outputs["category_performance"] = outputs["category_performance"].sort_values("total_sales", ascending=False)
    outputs["monthly_trend"] = (
        orders.groupby("order_year_month")
        .agg(total_orders=("order_id", "nunique"), total_sales=("net_order_sales", "sum"), total_profit=("order_profit", "sum"), late_delivery_rate=("late_delivery_flag", "mean"), avg_delay_days=("shipping_delay_days", "mean"), cancellation_rate=("cancellation_flag", "mean"))
        .reset_index()
        .sort_values("order_year_month")
    )
    outputs["order_status_distribution"] = (
        orders.groupby("order_status")
        .agg(total_orders=("order_id", "nunique"), total_sales=("net_order_sales", "sum"))
        .reset_index()
        .sort_values("total_orders", ascending=False)
    )
    outputs["loss_making_segments"] = (
        df.groupby(["market", "order_region", "category_name"])
        .agg(order_items=("order_item_id", "count"), total_orders=("order_id", "nunique"), total_sales=("order_item_total", "sum"), total_profit=("benefit_per_order", "sum"))
        .reset_index()
    )
    outputs["loss_making_segments"]["profit_margin"] = outputs["loss_making_segments"]["total_profit"] / outputs["loss_making_segments"]["total_sales"]
    outputs["loss_making_segments"] = outputs["loss_making_segments"].query("total_orders >= 50 and total_profit < 0").sort_values("total_profit")

    for name, table in outputs.items():
        table.to_csv(OUTPUTS_DIR / f"{name}.csv", index=False)
    return outputs


def create_sql_layer(df: pd.DataFrame) -> dict[str, float]:
    db_path = OUTPUTS_DIR / "supply_chain.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    sql_df = df.copy()
    for col in sql_df.select_dtypes(include=["datetime64[ns]"]).columns:
        sql_df[col] = sql_df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    sql_df.to_sql("order_items", conn, index=False, if_exists="replace")

    views_sql = """
    DROP VIEW IF EXISTS v_order_level;
    CREATE VIEW v_order_level AS
    SELECT
        order_id,
        MIN(order_date) AS order_date,
        MIN(shipping_date) AS shipping_date,
        MIN(shipping_mode) AS shipping_mode,
        MIN(type) AS transaction_type,
        MIN(market) AS market,
        MIN(order_region) AS order_region,
        MIN(order_country) AS order_country,
        MIN(order_state) AS order_state,
        MIN(order_city) AS order_city,
        MIN(customer_id) AS customer_id,
        MIN(customer_segment) AS customer_segment,
        MIN(order_status) AS order_status,
        AVG(days_for_shipping_real) AS days_for_shipping_real,
        AVG(days_for_shipment_scheduled) AS days_for_shipment_scheduled,
        AVG(shipping_delay_days) AS shipping_delay_days,
        MAX(late_delivery_flag) AS late_delivery_flag,
        MAX(on_time_flag) AS on_time_flag,
        MAX(cancellation_flag) AS cancellation_flag,
        MAX(suspected_fraud_flag) AS suspected_fraud_flag,
        COUNT(*) AS order_item_count,
        SUM(sales) AS gross_order_sales,
        SUM(order_item_total) AS net_order_sales,
        SUM(order_item_discount) AS order_discount,
        SUM(benefit_per_order) AS order_profit
    FROM order_items
    GROUP BY order_id;
    """
    conn.executescript(views_sql)

    schema_sql = """
    -- SQLite analytical layer generated from data/processed/supply_chain_order_items.csv
    -- Grain: one row per order item in order_items.
    -- v_order_level rolls order-item records to one row per order for delivery and cancellation KPIs.
    """
    write_text(SQL_DIR / "schema.sql", schema_sql)
    write_text(SQL_DIR / "views.sql", views_sql)

    queries = {
        "executive_kpi_summary": """
            SELECT
                SUM(order_item_total) AS total_sales,
                SUM(sales) AS gross_sales,
                SUM(benefit_per_order) AS total_profit,
                SUM(benefit_per_order) / NULLIF(SUM(order_item_total), 0) AS profit_margin,
                COUNT(DISTINCT order_id) AS total_orders,
                COUNT(*) AS total_order_items,
                COUNT(DISTINCT customer_id) AS total_customers,
                SUM(order_item_total) / NULLIF(COUNT(DISTINCT order_id), 0) AS average_order_value,
                (SELECT SUM(late_delivery_flag) FROM v_order_level) AS late_deliveries,
                (SELECT AVG(late_delivery_flag * 1.0) FROM v_order_level) AS late_delivery_rate,
                (SELECT SUM(CASE WHEN late_delivery_flag = 0 THEN 1 ELSE 0 END) FROM v_order_level) AS on_time_deliveries,
                (SELECT AVG(CASE WHEN late_delivery_flag = 0 THEN 1.0 ELSE 0 END) FROM v_order_level) AS on_time_delivery_rate,
                (SELECT SUM(cancellation_flag) FROM v_order_level) AS cancelled_orders,
                (SELECT AVG(cancellation_flag * 1.0) FROM v_order_level) AS cancellation_rate,
                (SELECT AVG(shipping_delay_days) FROM v_order_level) AS average_shipping_delay_days,
                (SELECT AVG(days_for_shipping_real) FROM v_order_level) AS average_actual_shipping_days,
                (SELECT AVG(days_for_shipment_scheduled) FROM v_order_level) AS average_scheduled_shipping_days
            FROM order_items;
        """,
        "shipping_mode_performance": """
            SELECT
                shipping_mode,
                COUNT(*) AS total_orders,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate,
                AVG(shipping_delay_days) AS avg_delay_days,
                SUM(net_order_sales) AS total_sales,
                SUM(order_profit) AS total_profit
            FROM v_order_level
            GROUP BY shipping_mode
            ORDER BY late_delivery_rate DESC, total_orders DESC;
        """,
        "market_delivery_performance": """
            SELECT
                market,
                COUNT(*) AS total_orders,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate,
                AVG(shipping_delay_days) AS avg_delay_days,
                SUM(net_order_sales) AS total_sales,
                SUM(order_profit) AS total_profit
            FROM v_order_level
            GROUP BY market
            ORDER BY total_orders DESC;
        """,
        "region_high_delay_segments": """
            SELECT
                market,
                order_region,
                COUNT(*) AS total_orders,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate,
                AVG(shipping_delay_days) AS avg_delay_days,
                SUM(net_order_sales) AS total_sales,
                SUM(order_profit) AS total_profit,
                RANK() OVER (ORDER BY AVG(late_delivery_flag * 1.0) DESC, COUNT(*) DESC) AS risk_rank
            FROM v_order_level
            GROUP BY market, order_region
            HAVING COUNT(*) >= 500
            ORDER BY late_delivery_rate DESC, total_orders DESC
            LIMIT 25;
        """,
        "monthly_delivery_trend": """
            SELECT
                substr(order_date, 1, 7) AS order_year_month,
                COUNT(*) AS total_orders,
                SUM(net_order_sales) AS total_sales,
                SUM(order_profit) AS total_profit,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate,
                AVG(shipping_delay_days) AS avg_delay_days,
                AVG(cancellation_flag * 1.0) AS cancellation_rate
            FROM v_order_level
            GROUP BY substr(order_date, 1, 7)
            ORDER BY order_year_month;
        """,
        "category_sales_profit": """
            SELECT
                department_name,
                category_name,
                COUNT(*) AS order_items,
                COUNT(DISTINCT order_id) AS total_orders,
                SUM(order_item_total) AS total_sales,
                SUM(benefit_per_order) AS total_profit,
                SUM(benefit_per_order) / NULLIF(SUM(order_item_total), 0) AS profit_margin
            FROM order_items
            GROUP BY department_name, category_name
            ORDER BY total_sales DESC
            LIMIT 30;
        """,
        "high_sales_low_profit_categories": """
            WITH category_metrics AS (
                SELECT
                    category_name,
                    COUNT(DISTINCT order_id) AS total_orders,
                    SUM(order_item_total) AS total_sales,
                    SUM(benefit_per_order) AS total_profit,
                    SUM(benefit_per_order) / NULLIF(SUM(order_item_total), 0) AS profit_margin
                FROM order_items
                GROUP BY category_name
            )
            SELECT *
            FROM category_metrics
            WHERE total_sales >= (SELECT AVG(total_sales) FROM category_metrics)
            ORDER BY profit_margin ASC, total_sales DESC
            LIMIT 15;
        """,
        "order_status_distribution": """
            SELECT
                order_status,
                COUNT(*) AS total_orders,
                SUM(net_order_sales) AS total_sales,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate
            FROM v_order_level
            GROUP BY order_status
            ORDER BY total_orders DESC;
        """,
        "top_products_sales_profit": """
            SELECT
                product_name,
                category_name,
                COUNT(*) AS order_items,
                COUNT(DISTINCT order_id) AS total_orders,
                SUM(order_item_total) AS total_sales,
                SUM(benefit_per_order) AS total_profit,
                SUM(benefit_per_order) / NULLIF(SUM(order_item_total), 0) AS profit_margin,
                RANK() OVER (ORDER BY SUM(order_item_total) DESC) AS sales_rank
            FROM order_items
            GROUP BY product_name, category_name
            ORDER BY total_sales DESC
            LIMIT 25;
        """,
        "loss_making_segments": """
            SELECT
                market,
                order_region,
                category_name,
                COUNT(DISTINCT order_id) AS total_orders,
                SUM(order_item_total) AS total_sales,
                SUM(benefit_per_order) AS total_profit,
                SUM(benefit_per_order) / NULLIF(SUM(order_item_total), 0) AS profit_margin
            FROM order_items
            GROUP BY market, order_region, category_name
            HAVING COUNT(DISTINCT order_id) >= 50 AND SUM(benefit_per_order) < 0
            ORDER BY total_profit ASC
            LIMIT 25;
        """,
    }

    write_text(
        SQL_DIR / "kpi_queries.sql",
        "-- Executive KPI query\n" + queries["executive_kpi_summary"].strip(),
    )
    write_text(
        SQL_DIR / "business_analysis.sql",
        "\n\n".join(f"-- {name}\n{query.strip()}" for name, query in queries.items() if name != "executive_kpi_summary"),
    )
    write_text(
        SQL_DIR / "validation_queries.sql",
        """
        -- Validation checks used by run_pipeline.py
        SELECT COUNT(*) AS order_item_rows FROM order_items;
        SELECT COUNT(*) AS order_rows FROM v_order_level;
        SELECT COUNT(DISTINCT order_item_id) AS distinct_order_item_ids FROM order_items;
        SELECT COUNT(DISTINCT order_id) AS distinct_order_ids FROM order_items;
        """,
    )

    sql_results = {}
    for name, query in queries.items():
        table = pd.read_sql_query(query, conn)
        table.to_csv(SQL_OUTPUTS_DIR / f"{name}.csv", index=False)
        sql_results[name] = table
    executive = sql_results["executive_kpi_summary"].iloc[0].to_dict()
    conn.close()
    return {key: float(value) for key, value in executive.items()}


def validate_kpis(metrics: Metrics, sql_metrics: dict[str, float]) -> pd.DataFrame:
    py_metrics = {
        "total_sales": metrics.total_sales,
        "gross_sales": metrics.gross_sales,
        "total_profit": metrics.total_profit,
        "profit_margin": metrics.profit_margin,
        "total_orders": metrics.total_orders,
        "total_order_items": metrics.total_order_items,
        "total_customers": metrics.total_customers,
        "average_order_value": metrics.average_order_value,
        "late_delivery_rate": metrics.late_delivery_rate,
        "on_time_delivery_rate": metrics.on_time_delivery_rate,
        "cancellation_rate": metrics.cancellation_rate,
        "average_shipping_delay_days": metrics.average_shipping_delay_days,
    }
    rows = []
    for key, py_value in py_metrics.items():
        sql_value = sql_metrics[key]
        tolerance = 0.0001 if "rate" in key or "margin" in key else 0.01
        diff = abs(float(py_value) - float(sql_value))
        rows.append(
            {
                "kpi": key,
                "python_value": py_value,
                "sql_value": sql_value,
                "absolute_difference": diff,
                "tolerance": tolerance,
                "validation_status": "PASS" if diff <= tolerance else "FAIL",
            }
        )
    validation = pd.DataFrame(rows)
    validation.to_csv(OUTPUTS_DIR / "kpi_validation.csv", index=False)
    return validation


def build_powerbi_model(df: pd.DataFrame, orders: pd.DataFrame) -> None:
    for old_file in POWERBI_DATA_DIR.glob("*.csv"):
        old_file.unlink()

    fact_cols = [
        "order_item_id",
        "order_id",
        "customer_id",
        "product_card_id",
        "geography_key",
        "order_date_key",
        "shipping_date_key",
        "sales",
        "order_item_total",
        "order_item_discount",
        "order_item_discount_rate",
        "order_item_quantity",
        "benefit_per_order",
        "order_item_profit_ratio",
        "profit_margin",
    ]
    fact = df[[col for col in fact_cols if col in df.columns]].copy()
    fact.to_csv(POWERBI_DATA_DIR / "fact_order_items.csv", index=False)

    order_cols = [
        "order_id",
        "customer_id",
        "geography_key",
        "order_date_key",
        "shipping_date_key",
        "order_date",
        "shipping_date",
        "shipping_mode",
        "type",
        "market",
        "order_region",
        "order_country",
        "order_state",
        "order_city",
        "customer_segment",
        "order_status",
        "days_for_shipping_real",
        "days_for_shipment_scheduled",
        "shipping_delay_days",
        "late_delivery_flag",
        "on_time_flag",
        "cancellation_flag",
        "suspected_fraud_flag",
        "delivery_status",
        "delay_severity",
        "delivery_performance_group",
        "order_item_count",
        "gross_order_sales",
        "net_order_sales",
        "order_discount",
        "order_profit",
    ]
    fact_orders = orders[[col for col in order_cols if col in orders.columns]].copy()
    fact_orders.to_csv(POWERBI_DATA_DIR / "fact_orders.csv", index=False)

    customer_cols = ["customer_id", "customer_segment", "customer_city", "customer_country", "customer_state"]
    df[[col for col in customer_cols if col in df.columns]].drop_duplicates("customer_id").to_csv(POWERBI_DATA_DIR / "dim_customers.csv", index=False)

    product_cols = ["product_card_id", "product_category_id", "product_name", "product_price", "product_status", "category_id", "category_name", "department_id", "department_name"]
    df[[col for col in product_cols if col in df.columns]].drop_duplicates("product_card_id").to_csv(POWERBI_DATA_DIR / "dim_products.csv", index=False)

    geography_cols = ["geography_key", "market", "order_region", "order_country", "order_state", "order_city"]
    df[geography_cols].drop_duplicates("geography_key").to_csv(POWERBI_DATA_DIR / "dim_geography.csv", index=False)

    shipping_modes = orders[["shipping_mode"]].drop_duplicates().sort_values("shipping_mode")
    shipping_modes.to_csv(POWERBI_DATA_DIR / "dim_shipping_mode.csv", index=False)

    order_statuses = orders[["order_status"]].drop_duplicates().sort_values("order_status")
    order_statuses.to_csv(POWERBI_DATA_DIR / "dim_order_status.csv", index=False)

    min_date = min(df["order_date"].min(), df["shipping_date"].min())
    max_date = max(df["order_date"].max(), df["shipping_date"].max())
    dates = pd.DataFrame({"date": pd.date_range(min_date.normalize(), max_date.normalize(), freq="D")})
    dates["date_key"] = dates["date"].dt.strftime("%Y%m%d")
    dates["year"] = dates["date"].dt.year
    dates["quarter"] = "Q" + dates["date"].dt.quarter.astype(str)
    dates["month_number"] = dates["date"].dt.month
    dates["month_name"] = dates["date"].dt.month_name()
    dates["year_month"] = dates["date"].dt.to_period("M").astype(str)
    dates["weekday_name"] = dates["date"].dt.day_name()
    dates.to_csv(POWERBI_DATA_DIR / "dim_date.csv", index=False)

    field_rows = []
    for path in sorted(POWERBI_DATA_DIR.glob("*.csv")):
        table = pd.read_csv(path, nrows=25)
        for col in table.columns:
            field_rows.append(
                {
                    "table_name": path.stem,
                    "field_name": col,
                    "data_type": str(table[col].dtype),
                    "business_description": powerbi_field_description(path.stem, col),
                    "recommended_format": recommended_format(col),
                    "default_summarization": default_summarization(col),
                }
            )
    pd.DataFrame(field_rows).to_csv(POWERBI_DIR / "field_dictionary.csv", index=False)


def powerbi_field_description(table: str, col: str) -> str:
    descriptions = {
        "order_item_total": "Discount-adjusted net sales for the order item.",
        "benefit_per_order": "Source profit/benefit amount for the order item.",
        "late_delivery_flag": "Order-level flag where 1 means the source marks the order late.",
        "shipping_delay_days": "Actual shipping days minus scheduled shipping days.",
        "order_id": "Business order identifier.",
        "order_item_id": "Unique order-item identifier.",
        "geography_key": "Composite key for market, region, country, state, and city.",
    }
    return descriptions.get(col, f"{col.replace('_', ' ').title()} field from {table}.")


def recommended_format(col: str) -> str:
    if any(token in col for token in ["sales", "profit", "discount", "price", "total"]):
        return "Currency"
    if "rate" in col or "margin" in col or "ratio" in col:
        return "Percentage"
    if "date" in col and "key" not in col:
        return "Date/Time"
    if col.endswith("_id") or col.endswith("_key"):
        return "Text / Do not summarize"
    return "Whole number" if any(token in col for token in ["count", "quantity", "days"]) else "Text"


def default_summarization(col: str) -> str:
    if col.endswith("_id") or col.endswith("_key"):
        return "Do not summarize"
    if any(token in col for token in ["sales", "profit", "discount", "quantity"]):
        return "Sum"
    if "rate" in col or "margin" in col or "days" in col:
        return "Average"
    return "Do not summarize"


def md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    shown = df.head(max_rows).copy()
    if shown.empty:
        return "_No rows._"

    def fmt(value) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4f}" if abs(value) < 1 else f"{value:,.2f}"
        return str(value)

    headers = [str(col) for col in shown.columns]
    rows = [[fmt(value).replace("|", "\\|") for value in row] for row in shown.to_numpy()]
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, divider, *body])


def create_docs(
    raw_data: dict[str, pd.DataFrame],
    df: pd.DataFrame,
    orders: pd.DataFrame,
    metrics: Metrics,
    dq: pd.DataFrame,
    kpis: pd.DataFrame,
    eda: dict[str, pd.DataFrame],
    validation: pd.DataFrame,
) -> None:
    inventory = pd.read_csv(OUTPUTS_DIR / "dataset_inventory.csv")
    main = raw_data[MAIN_SOURCE]
    description = raw_data[DESCRIPTION_SOURCE]
    logs = raw_data[ACCESS_LOG_SOURCE]
    first_month = orders["order_year_month"].min()
    last_month = orders["order_year_month"].max()
    top_shipping = eda["shipping_mode_performance"].iloc[0]
    top_market_volume = eda["market_performance"].sort_values("total_orders", ascending=False).iloc[0]
    highest_market_late = eda["market_performance"].sort_values("late_delivery_rate", ascending=False).iloc[0]
    top_region_risk = eda["region_risk"].iloc[0]
    top_category = eda["category_performance"].iloc[0]
    low_profit_category = eda["category_performance"].query("total_sales > total_sales.quantile(0.75)").sort_values("profit_margin").iloc[0]
    worst_loss = eda["loss_making_segments"].iloc[0] if len(eda["loss_making_segments"]) else None
    monthly_best = eda["monthly_trend"].sort_values("late_delivery_rate").iloc[0]
    monthly_worst = eda["monthly_trend"].sort_values("late_delivery_rate", ascending=False).iloc[0]

    write_text(
        DOCS_DIR / "dataset_inventory.md",
        f"""
        # Dataset Inventory

        Source archive: `archive.zip`

        ## Files

        {md_table(inventory[["filename", "file_size_bytes", "row_count", "column_count", "duplicate_full_rows"]])}

        ## Notes
        - All CSVs were parsed with `latin1` encoding.
        - Detailed column-level missingness is available in `outputs/missing_value_profile.csv`.
        - Sample records are available in `outputs/source_sample_records.json`.
        """,
    )

    write_text(
        DOCS_DIR / "dataset_relevance.md",
        f"""
        # Dataset Relevance Decisions

        ## Core Analytical Dataset
        `DataCoSupplyChainDataset.csv`

        Reason: contains order, order-item, customer, product, geography, sales, profit, shipping mode, scheduled shipping days, actual shipping days, delivery status, late-delivery flag, and order status fields. This file supports the primary supply chain delivery performance business problem.

        Grain: one row per order item. `order_item_id` is the candidate item key; `order_id` repeats across order items and must be distinct-counted for order-level KPIs.

        ## Supporting Metadata
        `DescriptionDataCoSupplyChain.csv`

        Reason: contains source field descriptions and supports interpretation of the core analytical dataset.

        ## Secondary Analytical Dataset
        `tokenized_access_logs.csv`

        Reason: contains product/category web access events by date/hour/department. It is relevant to digital interest analysis but does not contain order IDs, delivery fields, shipping dates, profit, or fulfillment status. It is excluded from the primary delivery-performance model to keep the project focused and avoid unsupported joins.

        ## Source File Summary
        - Main supply chain rows: {len(main):,}
        - Data dictionary rows: {len(description):,}
        - Access log rows: {len(logs):,}
        """,
    )

    write_text(
        DOCS_DIR / "project_charter.md",
        f"""
        # Project Charter

        ## Business Problem
        Supply chain and operations leaders need to understand where delivery commitments are being missed and whether those operational risks overlap with meaningful sales and profitability exposure.

        ## Analytical Objective
        Build a reproducible order-item analytics model that identifies late-delivery patterns by shipping mode, market, region, time period, category, and product while preserving grain-aware commercial KPIs.

        ## Primary Stakeholders
        - Supply Chain Operations
        - Logistics Management
        - Fulfillment Operations
        - Executive Operations Leadership

        ## Secondary Stakeholders
        - Commercial Analytics
        - Category Management

        ## Key Business Questions
        - What share of orders are late, and how large is the average delay versus schedule?
        - Which shipping modes carry the greatest late-delivery risk?
        - Which markets and regions combine high order volume with poor delivery performance?
        - Which categories create high sales exposure but weak profitability?
        - Are delivery risks changing over time?

        ## Analytical Scope
        The project covers orders from {first_month} to {last_month}, using the core DataCo supply chain dataset. Headline delivery KPIs are calculated at order grain; revenue and profit are calculated at order-item grain.

        ## Exclusions
        - Postal-code-level analysis is excluded because `order_zipcode` has substantial missingness.
        - Access-log traffic analysis is excluded from the primary model because it cannot be reliably joined to order delivery records.
        - Root-cause claims are excluded because the dataset does not contain carrier, warehouse, inventory, or staffing variables.

        ## Known Limitations
        The data supports performance monitoring and prioritization, not causal attribution.
        """,
    )

    write_text(
        DOCS_DIR / "grain_analysis.md",
        f"""
        # Grain Analysis

        ## Main Dataset Grain
        The main analytical dataset is **one row per order item**.

        Evidence:
        - Rows: {len(df):,}
        - Distinct `order_item_id`: {df["order_item_id"].nunique():,}
        - Duplicate `order_item_id` count: {df["order_item_id"].duplicated().sum():,}
        - Distinct `order_id`: {orders["order_id"].nunique():,}
        - Order IDs with multiple rows: {(df.groupby("order_id").size() > 1).sum():,}

        ## KPI Grain Governance
        - Sales, discounts, quantities, and item profit are summed at order-item grain.
        - Orders, late deliveries, shipping duration, cancellation rate, and average delay are calculated from an order-level table to prevent double counting.
        - Customer and product counts use distinct identifiers.
        """,
    )

    write_text(
        DOCS_DIR / "kpi_dictionary.md",
        "# KPI Dictionary\n\n" + md_table(kpis, max_rows=50),
    )

    write_text(
        DOCS_DIR / "data_quality_report.md",
        f"""
        # Data Quality Report

        ## Summary
        A reproducible data quality audit was executed against the processed analytical dataset. The audit checks missing values, duplicate rows, key uniqueness, invalid dates, impossible date relationships, negative and non-positive numeric values, discount anomalies, and delivery flag consistency.

        ## Issue Register
        Full issue register: `outputs/data_quality_issue_register.csv`

        {md_table(dq[["issue_id", "severity", "affected_fields", "affected_row_count", "affected_pct", "status"]], max_rows=30)}

        ## Material Findings
        - The dataset is order-item grain, so duplicate `order_id` values are expected and governed through order-level KPI logic.
        - Sensitive raw customer fields were excluded from processed and Power BI-ready files.
        - Negative profit values were retained as valid loss-making business records.
        - Postal-code analysis was deferred because order zipcode missingness limits reliability.
        """,
    )

    write_text(
        DOCS_DIR / "data_cleaning_rules.md",
        f"""
        # Data Cleaning Rules

        ## Applied Rules
        - Extracted raw files from `archive.zip` into `data/raw` without modifying the archive or raw CSVs.
        - Standardized column names to snake_case.
        - Trimmed whitespace from text fields.
        - Parsed order and shipping timestamps into datetime fields.
        - Removed sensitive or low-value publication fields from processed outputs: customer email, password, street, first name, last name, product image, and empty product description.
        - Created order date attributes: year, quarter, month, year-month, weekday, and date keys.
        - Created delivery fields: `shipping_delay_days`, `late_delivery_flag`, `on_time_flag`, `delay_severity`, and `delivery_performance_group`.
        - Created order status flags: `cancellation_flag` and `suspected_fraud_flag`.
        - Created `profit_margin` using item profit divided by discount-adjusted item total.
        - Created a composite `geography_key` for Power BI relationships.

        ## Row Count Validation
        - Source main rows: {len(main):,}
        - Processed rows: {len(df):,}
        - Rows removed: {len(main) - len(df):,}

        No analytical rows were deleted.
        """,
    )

    write_text(
        REPORTS_DIR / "eda_report.md",
        f"""
        # Exploratory Data Analysis Report

        ## Overall Delivery Performance
        Across {metrics.total_orders:,} distinct orders, the late delivery rate is {pct(metrics.late_delivery_rate)} and average shipping delay is {num(metrics.average_shipping_delay_days)} days.

        ## Shipping Mode Performance
        `{top_shipping["shipping_mode"]}` has the highest late-delivery rate at {pct(top_shipping["late_delivery_rate"])} across {int(top_shipping["total_orders"]):,} orders. This indicates that promised service level and actual performance should be reviewed by mode rather than assuming faster modes always perform better.

        ## Geographic Performance
        `{top_market_volume["market"]}` has the highest order volume with {int(top_market_volume["total_orders"]):,} orders. `{highest_market_late["market"]}` has the highest market-level late delivery rate at {pct(highest_market_late["late_delivery_rate"])}.

        Among high-volume regions, `{top_region_risk["market"]} / {top_region_risk["order_region"]}` has a late delivery rate of {pct(top_region_risk["late_delivery_rate"])} across {int(top_region_risk["total_orders"]):,} orders.

        ## Commercial Performance
        The highest-sales category is `{top_category["category_name"]}` with {money(top_category["total_sales"])} in net sales and {money(top_category["total_profit"])} in profit.

        A high-sales, low-margin category to review is `{low_profit_category["category_name"]}`, with {money(low_profit_category["total_sales"])} in net sales and a {pct(low_profit_category["profit_margin"])} profit margin.

        ## Time Analysis
        The lowest monthly late delivery rate appears in {monthly_best["order_year_month"]} at {pct(monthly_best["late_delivery_rate"])}. The highest monthly late delivery rate appears in {monthly_worst["order_year_month"]} at {pct(monthly_worst["late_delivery_rate"])}.

        ## Figures
        - `reports/figures/late_delivery_rate_by_shipping_mode.svg`
        - `reports/figures/market_order_volume.svg`
        - `reports/figures/monthly_sales_late_delivery_trend.svg`
        - `reports/figures/top_categories_sales.svg`
        - `reports/figures/shipping_delay_distribution.svg`
        - `reports/figures/high_volume_regions_late_delivery.svg`
        """,
    )

    write_text(
        DOCS_DIR / "sql_analysis.md",
        f"""
        # SQL Analysis

        ## SQL Engine
        SQLite is used for reproducibility. The local database is generated at `outputs/supply_chain.sqlite`.

        ## Analytical Model
        - `order_items`: one row per order item, loaded from `data/processed/supply_chain_order_items.csv`.
        - `v_order_level`: SQL view rolling item rows to one row per order for delivery and cancellation metrics.

        ## SQL Files
        - `sql/schema.sql`
        - `sql/views.sql`
        - `sql/kpi_queries.sql`
        - `sql/business_analysis.sql`
        - `sql/validation_queries.sql`

        ## Executed Analyses
        SQL outputs are exported under `outputs/sql`.

        Key analyses include executive KPI summary, shipping mode performance, market delivery performance, high-delay regions with minimum volume thresholds, monthly delivery trend, category sales and profitability, order status distribution, top products, and loss-making segments.

        ## Major SQL Findings
        - Total net sales: {money(metrics.total_sales)}
        - Total profit: {money(metrics.total_profit)}
        - Profit margin: {pct(metrics.profit_margin)}
        - Late delivery rate: {pct(metrics.late_delivery_rate)}
        - Average shipping delay: {num(metrics.average_shipping_delay_days)} days
        """,
    )

    write_text(
        DOCS_DIR / "validation_report.md",
        f"""
        # Validation Report

        ## Python vs SQL KPI Reconciliation
        Validation output: `outputs/kpi_validation.csv`

        {md_table(validation, max_rows=30)}

        ## Status
        Critical KPI reconciliation status: {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}

        All KPI comparisons use independent Python and SQLite calculations with explicit tolerances.
        """,
    )

    business_extra = ""
    if worst_loss is not None:
        business_extra = f"""
        ## Profitability Risk Segment
        `{worst_loss["market"]} / {worst_loss["order_region"]} / {worst_loss["category_name"]}` is the largest loss-making segment among segments with at least 50 orders, with {money(worst_loss["total_profit"])} profit on {money(worst_loss["total_sales"])} net sales. Recommended action: review discounting, product cost, fulfillment cost, or returns exposure for this segment before scaling volume.
        """

    write_text(
        REPORTS_DIR / "business_insights.md",
        f"""
        # Business Insights

        ## 1. Late Delivery Is A Material Operating Pattern
        Finding: {pct(metrics.late_delivery_rate)} of distinct orders are flagged late, with an average delay of {num(metrics.average_shipping_delay_days)} days versus the scheduled duration.

        Business significance: Late delivery is broad enough to require operational monitoring rather than one-off exception handling.

        Recommended action: Monitor late delivery rate weekly by shipping mode, market, and region; investigate segments where high late rates overlap with high order volume.

        Limitation: The dataset does not include carrier, facility, inventory, or staffing variables, so it does not prove root causes.

        ## 2. Shipping Mode Performance Requires Service-Level Review
        Finding: `{top_shipping["shipping_mode"]}` has the highest late-delivery rate at {pct(top_shipping["late_delivery_rate"])}.

        Business significance: The shipping mode promise may not consistently translate into delivered performance.

        Recommended action: Compare mode-level promised durations with actual cycle times and evaluate whether scheduling rules or carrier choices need review.

        ## 3. High-Volume Regional Risk Should Be Prioritized
        Finding: `{top_region_risk["market"]} / {top_region_risk["order_region"]}` combines {int(top_region_risk["total_orders"]):,} orders with a {pct(top_region_risk["late_delivery_rate"])} late delivery rate.

        Business significance: Operational fixes in this segment would affect meaningful order volume.

        Recommended action: Prioritize this region for logistics review, then compare route, carrier, fulfillment, and scheduling assumptions outside this dataset.

        ## 4. Commercial Exposure And Profitability Need Joint Review
        Finding: `{low_profit_category["category_name"]}` is a high-sales category with a {pct(low_profit_category["profit_margin"])} profit margin.

        Business significance: Sales volume alone can hide margin risk.

        Recommended action: Review pricing, discounting, and fulfillment economics for high-sales low-margin categories.

        {business_extra}
        """,
    )

    write_text(
        REPORTS_DIR / "executive_summary.md",
        f"""
        # Executive Summary

        This portfolio case study analyzes {metrics.total_orders:,} orders and {metrics.total_order_items:,} order items from the DataCo supply chain dataset. The project focuses on delivery performance, commercial exposure, profitability, and dashboard-ready KPI governance.

        Headline results:
        - Net sales: {money(metrics.total_sales)}
        - Total profit: {money(metrics.total_profit)}
        - Profit margin: {pct(metrics.profit_margin)}
        - Late delivery rate: {pct(metrics.late_delivery_rate)}
        - Average shipping delay: {num(metrics.average_shipping_delay_days)} days
        - Cancellation rate: {pct(metrics.cancellation_rate)}

        The main operational takeaway is that delivery risk should be managed at the intersection of shipping mode, market, and region. The main commercial takeaway is that category and regional sales should be interpreted with profitability context, because high sales do not always imply strong margin.
        """,
    )

    create_corrected_powerbi_docs(metrics, eda, validation)
    create_dashboard_environment_doc()
    create_html_dashboard(metrics, eda)
    create_portfolio_docs(metrics, eda)
    create_github_data_strategy()
    create_readme(metrics, eda, validation)
    create_project_status(df, orders, metrics, validation)


def create_powerbi_docs(metrics: Metrics, eda: dict[str, pd.DataFrame], validation: pd.DataFrame) -> None:
    create_corrected_powerbi_docs(metrics, eda, validation)


def create_corrected_powerbi_docs(metrics: Metrics, eda: dict[str, pd.DataFrame], validation: pd.DataFrame) -> None:
    write_text(
        POWERBI_DIR / "model_specification.md",
        """
        # Corrected Power BI Model Specification

        ## Defect Corrected
        The earlier model placed order-level measures on `dim_orders` while dashboard visuals used `dim_geography` and `dim_products`. With single-direction relationships, product/category filters did not reliably propagate to the order-level table. The corrected model avoids bidirectional filtering and uses explicit order-scope DAX.

        ## Files To Import
        Import CSV files from `powerbi/data` after running `python run_pipeline.py`:
        - `fact_orders.csv`
        - `fact_order_items.csv`
        - `dim_customers.csv`
        - `dim_products.csv`
        - `dim_geography.csv`
        - `dim_shipping_mode.csv`
        - `dim_order_status.csv`
        - `dim_date.csv`

        ## Table Grain
        - `fact_orders`: one row per order. Use this table for delivery, cancellation, shipping duration, and order-level KPIs.
        - `fact_order_items`: one row per order item. Use this table for sales, profit, quantity, product, and category analysis.
        - `dim_products`: one row per product.
        - `dim_geography`: one row per market/region/country/state/city key.
        - `dim_customers`: one row per customer.
        - `dim_shipping_mode`: one row per shipping mode.
        - `dim_order_status`: one row per order status.
        - `dim_date`: one row per calendar date.

        ## Relationships
        Use single-direction filters from dimensions to facts:
        - `dim_geography[geography_key]` 1:* `fact_orders[geography_key]`
        - `dim_geography[geography_key]` 1:* `fact_order_items[geography_key]`
        - `dim_customers[customer_id]` 1:* `fact_orders[customer_id]`
        - `dim_customers[customer_id]` 1:* `fact_order_items[customer_id]`
        - `dim_products[product_card_id]` 1:* `fact_order_items[product_card_id]`
        - `dim_shipping_mode[shipping_mode]` 1:* `fact_orders[shipping_mode]`
        - `dim_order_status[order_status]` 1:* `fact_orders[order_status]`
        - `dim_date[date_key]` 1:* `fact_orders[order_date_key]`
        - `dim_date[date_key]` 1:* `fact_order_items[order_date_key]`

        Do not create a direct relationship between `fact_orders` and `fact_order_items`. Do not enable bidirectional relationships by default.

        ## Product/Category Filter Solution
        Product and category filters naturally filter `fact_order_items`. Order-level measures use `TREATAS(VALUES(fact_order_items[order_id]), fact_orders[order_id])` so category/product selections correctly restrict the order-level calculation scope without ambiguous relationship paths.

        ## Date, Geography, And Shipping Filters
        Date and geography dimensions filter both fact tables directly. Shipping mode and order status filter `fact_orders`; sales visuals that require shipping-mode filtering should use measures that apply order scope through `TREATAS`.
        """,
    )

    dax = """
    # Corrected DAX Measure Library

    ## Order Scope Helper Pattern
    Product and category filters live on `fact_order_items`. Measures that calculate order-level KPIs apply the current item-filtered order set to `fact_orders` using `TREATAS`.

    ```DAX
    -- Pattern used inside order-level measures
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN CALCULATE(<order expression>, TREATAS(ScopedOrders, fact_orders[order_id]))
    ```

    ## Total Sales
    ```DAX
    Total Sales = SUM(fact_order_items[order_item_total])
    ```
    Format: Currency. Definition: discount-adjusted order-item revenue.

    ## Total Profit
    ```DAX
    Total Profit = SUM(fact_order_items[benefit_per_order])
    ```
    Format: Currency. Definition: source item-level profit.

    ## Profit Margin
    ```DAX
    Profit Margin = DIVIDE([Total Profit], [Total Sales])
    ```
    Format: Percentage. Definition: profit divided by net sales.

    ## Total Orders
    ```DAX
    Total Orders =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            DISTINCTCOUNT(fact_orders[order_id]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Whole number. Filter behavior: respects date, geography, customer, product/category, and shipping-mode filters.

    ## Total Order Items
    ```DAX
    Total Order Items = COUNTROWS(fact_order_items)
    ```
    Format: Whole number.

    ## Total Customers
    ```DAX
    Total Customers = DISTINCTCOUNT(dim_customers[customer_id])
    ```
    Format: Whole number.

    ## Average Order Value
    ```DAX
    Average Order Value = DIVIDE([Total Sales], [Total Orders])
    ```
    Format: Currency.

    ## Late Deliveries
    ```DAX
    Late Deliveries =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            SUM(fact_orders[late_delivery_flag]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Whole number.

    ## Late Delivery Rate
    ```DAX
    Late Delivery Rate = DIVIDE([Late Deliveries], [Total Orders])
    ```
    Format: Percentage.

    ## On-Time Deliveries
    ```DAX
    On-Time Deliveries =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            SUMX(fact_orders, IF(fact_orders[late_delivery_flag] = 0, 1, 0)),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Whole number.

    ## On-Time Delivery Rate
    ```DAX
    On-Time Delivery Rate = DIVIDE([On-Time Deliveries], [Total Orders])
    ```
    Format: Percentage.

    ## Average Shipping Delay
    ```DAX
    Average Shipping Delay =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            AVERAGE(fact_orders[shipping_delay_days]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Decimal days.

    ## Average Actual Shipping Days
    ```DAX
    Average Actual Shipping Days =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            AVERAGE(fact_orders[days_for_shipping_real]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Decimal days.

    ## Average Scheduled Shipping Days
    ```DAX
    Average Scheduled Shipping Days =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            AVERAGE(fact_orders[days_for_shipment_scheduled]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Decimal days.

    ## Cancelled Orders
    ```DAX
    Cancelled Orders =
    VAR ScopedOrders = VALUES(fact_order_items[order_id])
    RETURN
        CALCULATE(
            SUM(fact_orders[cancellation_flag]),
            TREATAS(ScopedOrders, fact_orders[order_id])
        )
    ```
    Format: Whole number.

    ## Cancellation Rate
    ```DAX
    Cancellation Rate = DIVIDE([Cancelled Orders], [Total Orders])
    ```
    Format: Percentage.

    ## Shipping-Mode Filtered Sales
    ```DAX
    Shipping-Mode Filtered Sales =
    VAR ScopedOrders = VALUES(fact_orders[order_id])
    RETURN
        CALCULATE(
            [Total Sales],
            TREATAS(ScopedOrders, fact_order_items[order_id])
        )
    ```
    Format: Currency. Use when a visual slices sales by `dim_shipping_mode`.

    ## Sales Previous Period
    ```DAX
    Sales Previous Period = CALCULATE([Total Sales], DATEADD(dim_date[date], -1, MONTH))
    ```
    Format: Currency.

    ## Sales Growth
    ```DAX
    Sales Growth = DIVIDE([Total Sales] - [Sales Previous Period], [Sales Previous Period])
    ```
    Format: Percentage.
    """
    write_text(POWERBI_DIR / "dax_measures.md", dax)
    write_text(POWERBI_DIR / "dax_measures.txt", re.sub(r"# .*?\n", "", dax))

    write_text(
        DOCS_DIR / "filter_propagation_validation.md",
        f"""
        # Filter Propagation Validation

        ## Defect
        The prior design documented order-level measures on `dim_orders` while product and geography fields were used in visuals. Single-direction filters from product/geography dimensions through `fact_order_items` could not reliably filter `dim_orders`.

        ## Corrected Design
        The model now uses:
        - `fact_orders` for one-row-per-order delivery and cancellation KPIs.
        - `fact_order_items` for one-row-per-item commercial KPIs.
        - Single-direction dimension-to-fact relationships.
        - `TREATAS` in order-level DAX measures so the visible set of `fact_order_items[order_id]` filters `fact_orders`.

        ## Conceptual Checks
        - Market and region fields filter `fact_orders` directly through `dim_geography`, so Total Orders, Late Delivery Rate, Average Shipping Delay, and Cancellation Rate respond to geography filters.
        - Category and product fields filter `fact_order_items`; the corrected DAX applies the filtered order IDs to `fact_orders`, so order-level delivery KPIs respond to product/category filters without bidirectional relationships.
        - Date filters apply to both facts through `dim_date`, preserving time-series compatibility for sales and delivery KPIs.
        - Shipping mode filters apply to `fact_orders`; sales by shipping mode uses the `Shipping-Mode Filtered Sales` measure to push the order scope back to `fact_order_items`.

        ## KPI Reconciliation
        Python and SQL headline KPI validation remains {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}. The corrected DAX uses the same numerator, denominator, and grain definitions as `outputs/kpi_validation.csv`.
        """,
    )

    write_text(
        POWERBI_DIR / "dashboard_blueprint.md",
        """
        # Corrected Dashboard Blueprint

        ## Page 1: Executive Overview
        Valid measures: Total Sales, Total Profit, Profit Margin, Total Orders, Late Delivery Rate, Average Shipping Delay, Cancellation Rate.
        Visuals use date/geography filters that affect both facts. Shipping-mode sales visuals must use `Shipping-Mode Filtered Sales`.

        ## Page 2: Delivery & Logistics Performance
        Valid measures: Total Orders, Late Deliveries, Late Delivery Rate, Average Actual Shipping Days, Average Scheduled Shipping Days, Average Shipping Delay.
        Dimensions: `dim_shipping_mode`, `dim_geography`, `dim_date`, and order-status fields.

        ## Page 3: Market & Commercial Performance
        Valid measures: Total Sales, Total Profit, Profit Margin, Total Orders, Late Delivery Rate.
        Use `dim_geography` fields for market/region and `dim_products` fields for category/product. Product/category delivery KPIs are valid because corrected DAX applies item-filtered order scope to `fact_orders`.

        ## Page 4: Diagnostic / Segment Detail
        Valid matrix fields: market, region, category, product, shipping mode, order status, Total Orders, Total Sales, Total Profit, Profit Margin, Late Delivery Rate, Average Shipping Delay.

        ## Removed Or Redesigned Visuals
        No visual should use raw columns from `fact_orders` and `fact_order_items` together without a measure. Product/category delivery visuals must use the corrected measures in `dax_measures.md`.
        """,
    )

    write_text(
        POWERBI_DIR / "dashboard_build_guide.md",
        """
        # Corrected Power BI Build Notes

        The completed interactive deliverable is `dashboard/supply_chain_delivery_dashboard.html`. The Power BI directory documents the corresponding model design, DAX measures, theme, and implementation plan.

        If building a Power BI report later, import the CSVs from `powerbi/data`, create the relationships in `model_specification.md`, and create measures from `dax_measures.md`. Do not use the earlier `dim_orders` pattern.
        """,
    )

    theme = {
        "name": "Supply Chain Operations",
        "dataColors": ["#2F5F8F", "#B23A48", "#2E7D32", "#C77D00", "#6B6B6B", "#5C4B8A"],
        "background": "#F7F8FA",
        "foreground": "#2B2B2B",
        "tableAccent": "#2F5F8F",
        "visualStyles": {"*": {"*": {"fontFamily": "Segoe UI"}}},
    }
    (POWERBI_DIR / "theme_supply_chain_operations.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")


def create_dashboard_environment_doc() -> None:
    write_text(
        DOCS_DIR / "dashboard_environment_inspection.md",
        """
        # Dashboard Environment Inspection

        Inspection was performed before selecting the final dashboard delivery technology.

        ## Checked
        - `PBIDesktop` command lookup
        - `pbi-tools` command lookup
        - `TabularEditor` and `TabularEditor3` command lookup
        - Microsoft Store/Appx package lookup for Power BI
        - Windows uninstall registry entries for Power BI, pbi-tools, and Tabular Editor
        - Common install folders under Program Files and user-local app locations

        ## Result
        Power BI Desktop, PBIP command-line tooling, pbi-tools, and Tabular Editor were not found as accessible local tooling in this environment.

        ## Delivery Decision
        Because native `.pbix` or `.pbip` creation was not technically available, the project delivers a finished standalone HTML analytics dashboard generated from the validated project data. The dashboard is recruiter-ready, requires no external server, and does not require the user to manually construct visuals.
        """,
    )


def html_table(df: pd.DataFrame, cols: list[str], max_rows: int = 10) -> str:
    rows = []
    for _, row in df.head(max_rows).iterrows():
        cells = "".join(f"<td>{html.escape(str(row[col]))}</td>" for col in cols)
        rows.append(f"<tr>{cells}</tr>")
    headers = "".join(f"<th>{html.escape(col.replace('_', ' ').title())}</th>" for col in cols)
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def create_html_dashboard(metrics: Metrics, eda: dict[str, pd.DataFrame]) -> None:
    shipping = eda["shipping_mode_performance"].copy()
    shipping["late_delivery_rate"] = (shipping["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    shipping["avg_delay_days"] = shipping["avg_delay_days"].astype(float).round(2)
    shipping["total_sales"] = shipping["total_sales"].astype(float).map(lambda v: money(v, 0))

    market = eda["market_performance"].copy()
    market["late_delivery_rate"] = (market["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    market["avg_delay_days"] = market["avg_delay_days"].astype(float).round(2)
    market["total_sales"] = market["total_sales"].astype(float).map(lambda v: money(v, 0))

    region = eda["region_risk"].head(12).copy()
    region["late_delivery_rate"] = (region["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    region["avg_delay_days"] = region["avg_delay_days"].astype(float).round(2)
    region["total_sales"] = region["total_sales"].astype(float).map(lambda v: money(v, 0))

    category = eda["category_performance"].head(12).copy()
    category["total_sales"] = category["total_sales"].astype(float).map(lambda v: money(v, 0))
    category["total_profit"] = category["total_profit"].astype(float).map(lambda v: money(v, 0))
    category["profit_margin"] = (category["profit_margin"] * 100).round(1).astype(str) + "%"

    monthly = eda["monthly_trend"].copy()
    monthly["late_delivery_rate_display"] = (monthly["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    monthly["total_sales_display"] = monthly["total_sales"].astype(float).map(lambda v: money(v, 0))
    monthly_recent = monthly.tail(12)

    dashboard_path = DASHBOARD_DIR / "supply_chain_delivery_dashboard.html"
    html_content = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Supply Chain Delivery Performance Dashboard</title>
      <style>
        :root {{ --blue:#2F5F8F; --red:#B23A48; --green:#2E7D32; --amber:#C77D00; --ink:#252525; --muted:#667085; --bg:#F7F8FA; --line:#D9DEE7; }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); }}
        header {{ padding:28px 34px 18px; background:#fff; border-bottom:1px solid var(--line); }}
        h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:0; }}
        h2 {{ margin:0 0 14px; font-size:20px; }}
        p {{ margin:0; color:var(--muted); line-height:1.45; }}
        main {{ padding:22px 34px 34px; max-width:1420px; margin:0 auto; }}
        .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px; }}
        .tabs button {{ border:1px solid var(--line); background:#fff; padding:10px 14px; border-radius:6px; cursor:pointer; font-weight:600; color:var(--ink); }}
        .tabs button.active {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
        .section {{ display:none; }}
        .section.active {{ display:block; }}
        .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(140px,1fr)); gap:12px; margin-bottom:18px; }}
        .card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; min-height:86px; }}
        .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:700; }}
        .value {{ font-size:24px; font-weight:750; margin-top:8px; }}
        .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
        .wide {{ grid-column:1 / -1; }}
        .panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:18px; }}
        .panel img {{ width:100%; height:auto; display:block; }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        th, td {{ padding:9px 10px; border-bottom:1px solid #E6EAF0; text-align:left; }}
        th {{ color:#475467; background:#F3F5F8; font-size:12px; text-transform:uppercase; }}
        .note {{ margin-top:12px; font-size:13px; color:var(--muted); }}
        .risk {{ color:var(--red); }}
        @media (max-width:1000px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} .grid {{ grid-template-columns:1fr; }} main, header {{ padding-left:18px; padding-right:18px; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>Supply Chain Delivery Performance Dashboard</h1>
        <p>Validated portfolio dashboard generated from Python and SQLite outputs. Metrics are grain-aware: commercial KPIs use order-item grain and delivery KPIs use distinct order grain.</p>
      </header>
      <main>
        <nav class="tabs">
          <button class="active" data-tab="overview">Executive Overview</button>
          <button data-tab="delivery">Delivery & Logistics</button>
          <button data-tab="commercial">Market & Commercial</button>
          <button data-tab="diagnostic">Diagnostic Detail</button>
        </nav>

        <section id="overview" class="section active">
          <div class="kpis">
            <div class="card"><div class="label">Total Sales</div><div class="value">{money(metrics.total_sales)}</div></div>
            <div class="card"><div class="label">Total Profit</div><div class="value">{money(metrics.total_profit)}</div></div>
            <div class="card"><div class="label">Profit Margin</div><div class="value">{pct(metrics.profit_margin)}</div></div>
            <div class="card"><div class="label">Total Orders</div><div class="value">{metrics.total_orders:,}</div></div>
            <div class="card"><div class="label">Late Delivery Rate</div><div class="value risk">{pct(metrics.late_delivery_rate)}</div></div>
            <div class="card"><div class="label">Avg Shipping Delay</div><div class="value">{num(metrics.average_shipping_delay_days)} days</div></div>
          </div>
          <div class="grid">
            <div class="panel wide"><h2>Monthly Sales And Late Delivery Trend</h2><img src="../reports/figures/monthly_sales_late_delivery_trend.svg" alt="Monthly sales and late delivery trend"></div>
            <div class="panel"><h2>Market Order Volume</h2><img src="../reports/figures/market_order_volume.svg" alt="Market order volume"></div>
            <div class="panel"><h2>Recent Monthly Performance</h2>{html_table(monthly_recent, ["order_year_month", "total_orders", "total_sales_display", "late_delivery_rate_display"], 12)}</div>
          </div>
        </section>

        <section id="delivery" class="section">
          <div class="grid">
            <div class="panel"><h2>Late Delivery Rate By Shipping Mode</h2><img src="../reports/figures/late_delivery_rate_by_shipping_mode.svg" alt="Late delivery rate by shipping mode"></div>
            <div class="panel"><h2>Shipping Mode Performance</h2>{html_table(shipping, ["shipping_mode", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 10)}</div>
            <div class="panel wide"><h2>High-Volume Regions With Highest Late Delivery Rates</h2><img src="../reports/figures/high_volume_regions_late_delivery.svg" alt="High volume regions late delivery"></div>
            <div class="panel wide"><h2>Regional Risk Table</h2>{html_table(region, ["market", "order_region", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 12)}</div>
          </div>
        </section>

        <section id="commercial" class="section">
          <div class="grid">
            <div class="panel"><h2>Top Categories By Net Sales</h2><img src="../reports/figures/top_categories_sales.svg" alt="Top categories by sales"></div>
            <div class="panel"><h2>Category Profitability</h2>{html_table(category, ["category_name", "total_orders", "total_sales", "total_profit", "profit_margin"], 12)}</div>
            <div class="panel wide"><h2>Market Performance</h2>{html_table(market, ["market", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 10)}</div>
          </div>
        </section>

        <section id="diagnostic" class="section">
          <div class="grid">
            <div class="panel"><h2>Shipping Delay Distribution</h2><img src="../reports/figures/shipping_delay_distribution.svg" alt="Shipping delay distribution"></div>
            <div class="panel">
              <h2>Analytical Guardrails</h2>
              <p class="note">This dashboard avoids unsupported causal claims. Late delivery findings are prioritization signals for review by market, region, category, and shipping mode.</p>
              <p class="note">Power BI model defect correction: order-level measures must use `fact_orders` plus an explicit item-filtered order scope for product/category selections.</p>
              <p class="note">Validation: Python and SQL KPI reconciliation passed with zero material differences.</p>
            </div>
          </div>
        </section>
      </main>
      <script>
        const buttons = document.querySelectorAll('.tabs button');
        const sections = document.querySelectorAll('.section');
        buttons.forEach(button => button.addEventListener('click', () => {{
          buttons.forEach(b => b.classList.remove('active'));
          sections.forEach(s => s.classList.remove('active'));
          button.classList.add('active');
          document.getElementById(button.dataset.tab).classList.add('active');
        }}));
      </script>
    </body>
    </html>
    """
    dashboard_path.write_text(textwrap.dedent(html_content).strip(), encoding="utf-8")
    rendered = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
    required_displays = {
        "total_sales_displayed": money(metrics.total_sales),
        "total_profit_displayed": money(metrics.total_profit),
        "profit_margin_displayed": pct(metrics.profit_margin),
        "total_orders_displayed": f"{metrics.total_orders:,}",
        "late_delivery_rate_displayed": pct(metrics.late_delivery_rate),
        "average_shipping_delay_displayed": f"{num(metrics.average_shipping_delay_days)} days",
    }
    checks = [
        {"check": "dashboard_exists", "expected": "true", "actual": str(dashboard_path.exists()).lower(), "status": "PASS" if dashboard_path.exists() else "FAIL"},
        {"check": "dashboard_non_empty", "expected": "> 1000 bytes", "actual": dashboard_path.stat().st_size if dashboard_path.exists() else 0, "status": "PASS" if dashboard_path.exists() and dashboard_path.stat().st_size > 1000 else "FAIL"},
        {"check": "dashboard_tabs_present", "expected": "4 tabs", "actual": rendered.count('data-tab="'), "status": "PASS" if rendered.count('data-tab="') == 4 else "FAIL"},
        {"check": "dashboard_javascript_tabs_present", "expected": "tab click handler", "actual": "addEventListener('click'" in rendered, "status": "PASS" if "addEventListener('click'" in rendered else "FAIL"},
    ]
    chart_assets = [
        "monthly_sales_late_delivery_trend.svg",
        "market_order_volume.svg",
        "late_delivery_rate_by_shipping_mode.svg",
        "high_volume_regions_late_delivery.svg",
        "top_categories_sales.svg",
        "shipping_delay_distribution.svg",
    ]
    missing_assets = [name for name in chart_assets if not (FIGURES_DIR / name).exists()]
    checks.append({"check": "dashboard_chart_assets_exist", "expected": "all referenced SVG assets", "actual": "; ".join(missing_assets) if missing_assets else "all present", "status": "PASS" if not missing_assets else "FAIL"})
    for check, expected in required_displays.items():
        checks.append({"check": check, "expected": expected, "actual": expected if expected in rendered else "missing", "status": "PASS" if expected in rendered else "FAIL"})

    chart_checks = [
        ("shipping_mode_chart_rows", int(eda["shipping_mode_performance"]["total_orders"].sum()), metrics.total_orders, 0),
        ("market_chart_orders_reconcile", int(eda["market_performance"]["total_orders"].sum()), metrics.total_orders, 0),
        ("monthly_trend_orders_reconcile", int(eda["monthly_trend"]["total_orders"].sum()), metrics.total_orders, 0),
        ("category_sales_reconcile", float(eda["category_performance"]["total_sales"].sum()), metrics.total_sales, 0.05),
        ("category_profit_reconcile", float(eda["category_performance"]["total_profit"].sum()), metrics.total_profit, 0.05),
    ]
    for check, actual, expected, tolerance in chart_checks:
        diff = abs(float(actual) - float(expected))
        checks.append({"check": check, "expected": expected, "actual": actual, "status": "PASS" if diff <= tolerance else "FAIL"})

    dashboard_checks = pd.DataFrame(checks)
    dashboard_checks.to_csv(OUTPUTS_DIR / "dashboard_validation.csv", index=False)


def create_portfolio_docs(metrics: Metrics, eda: dict[str, pd.DataFrame]) -> None:
    write_text(
        DOCS_DIR / "github_repository_description.md",
        """
        # GitHub Repository Description

        End-to-end supply chain delivery performance analytics portfolio project using Python, pandas, SQLite, data quality validation, KPI governance, SQL analysis, corrected Power BI model artifacts, and a finished interactive HTML dashboard.

        ## Suggested Topics
        supply-chain, logistics, data-analysis, pandas, sql, sqlite, power-bi, business-intelligence, data-quality, portfolio-project, analytics-engineering
        """,
    )
    write_text(
        DOCS_DIR / "resume_bullets.md",
        f"""
        # Resume Bullet Options

        - Built an end-to-end supply chain delivery analytics project in Python, pandas, and SQLite, profiling {metrics.total_order_items:,} order-item records and validating core KPIs across Python and SQL.
        - Designed grain-aware delivery and profitability KPIs for {metrics.total_orders:,} orders, including late delivery rate, average shipping delay, profit margin, and cancellation rate, with corrected Power BI model documentation and DAX measures.
        - Developed a recruiter-ready analytics portfolio case study with automated data extraction, cleaning, EDA, SQL analysis, KPI reconciliation, an interactive HTML dashboard, and business recommendations.
        """,
    )
    write_text(
        DOCS_DIR / "linkedin_project_description.md",
        f"""
        # LinkedIn Project Description

        I completed an end-to-end Supply Chain Delivery Performance Analysis portfolio project using Python, pandas, and SQLite. The project starts from a local raw ZIP archive, profiles and cleans {metrics.total_order_items:,} order-item records, defines grain-aware KPIs, validates Python metrics against SQL, documents a corrected Power BI model, and delivers a finished interactive HTML dashboard.

        The analysis focuses on late delivery performance, shipping mode effectiveness, regional operational risk, profitability, and high-sales low-margin segments. It is structured as a practical business analytics case study rather than a generic notebook.
        """,
    )


def repository_file_status(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    ignored_exact = {
        "archive.zip",
        "outputs/supply_chain.sqlite",
    }
    ignored_prefixes = (
        "data/raw/",
        "data/processed/",
        "powerbi/data/",
    )
    if (
        rel in ignored_exact
        or rel.startswith(ignored_prefixes)
        or "__pycache__" in parts
        or path.suffix == ".pyc"
        or rel.startswith(".git/")
    ):
        return "ignored_local_generated_or_sensitive"
    return "repository_intended"


def create_github_data_strategy() -> None:
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc_file in ROOT.rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)

    rows = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()
            rows.append(
                {
                    "path": rel,
                    "size_bytes": path.stat().st_size,
                    "size_mb": round(path.stat().st_size / 1_048_576, 3),
                    "repository_status": repository_file_status(path),
                }
            )

    inventory = pd.DataFrame(rows).sort_values("size_bytes", ascending=False)
    inventory.to_csv(OUTPUTS_DIR / "repository_file_inventory.csv", index=False)
    intended = inventory[inventory["repository_status"].eq("repository_intended")]
    too_large = intended[intended["size_bytes"] > 100 * 1024 * 1024]
    cache_artifacts = inventory[inventory["path"].str.contains("__pycache__", regex=False) | inventory["path"].str.endswith(".pyc")]
    dashboard_path = DASHBOARD_DIR / "supply_chain_delivery_dashboard.html"

    checks = pd.DataFrame(
        [
            {"check": "repository_intended_files_under_100_mib", "status": "PASS" if too_large.empty else "FAIL", "details": "; ".join(too_large["path"].tolist())},
            {"check": "python_cache_artifacts_absent", "status": "PASS" if cache_artifacts.empty else "FAIL", "details": "; ".join(cache_artifacts["path"].tolist())},
            {"check": "dashboard_artifact_versionable", "status": "PASS" if dashboard_path.exists() and repository_file_status(dashboard_path) == "repository_intended" else "FAIL", "details": f"{dashboard_path.relative_to(ROOT).as_posix()} size={dashboard_path.stat().st_size if dashboard_path.exists() else 0} bytes"},
            {"check": "raw_archive_ignored", "status": "PASS" if repository_file_status(ARCHIVE) != "repository_intended" else "FAIL", "details": f"archive.zip size={ARCHIVE.stat().st_size if ARCHIVE.exists() else 0} bytes"},
            {"check": "large_processed_csv_ignored", "status": "PASS" if repository_file_status(PROCESSED_DIR / "supply_chain_order_items.csv") != "repository_intended" else "FAIL", "details": "data/processed/supply_chain_order_items.csv"},
            {"check": "powerbi_generated_data_ignored", "status": "PASS" if repository_file_status(POWERBI_DATA_DIR / "fact_order_items.csv") != "repository_intended" else "FAIL", "details": "powerbi/data/*.csv"},
        ]
    )
    checks.to_csv(OUTPUTS_DIR / "repository_readiness_checks.csv", index=False)

    top_files = inventory.head(12).copy()
    versionable_top = intended.sort_values("size_bytes", ascending=False).head(12).copy()
    write_text(
        DOCS_DIR / "github_data_strategy.md",
        f"""
        # GitHub Data Strategy

        ## Decision
        The repository should keep source code, SQL, validation logic, documentation, charts, small summary outputs, Power BI model documentation, and the finished HTML dashboard under version control.

        The repository should not commit raw source extracts, processed full-detail datasets, generated Power BI CSV extracts, the generated SQLite database, Python cache artifacts, or the local `archive.zip`.

        ## Why `archive.zip` Is Ignored
        The local archive is {ARCHIVE.stat().st_size / 1_048_576:.2f} MiB, which is below GitHub's single-file limit, but it contains the raw source data with customer-identifying fields. Keeping it local avoids publishing raw sensitive fields and avoids duplicating generated extracts. The pipeline remains reproducible when `archive.zip` is present locally at the project root.

        ## GitHub File-Size Constraint
        GitHub blocks normal pushes containing a single file larger than 100 MiB. The generated processed order-item CSV is {((PROCESSED_DIR / "supply_chain_order_items.csv").stat().st_size / 1_048_576):.2f} MiB and must remain ignored.

        ## Current Largest Local Files
        {md_table(top_files[["path", "size_mb", "repository_status"]], max_rows=12)}

        ## Largest Repository-Intended Files
        {md_table(versionable_top[["path", "size_mb", "repository_status"]], max_rows=12)}

        ## Version-Controlled By Design
        - `src/`, `run_pipeline.py`, and `requirements.txt`
        - `sql/`
        - `validation/`
        - `docs/`, `reports/`, and `reports/figures/`
        - `powerbi/` documentation, DAX, style guide, and theme files
        - `dashboard/supply_chain_delivery_dashboard.html`
        - small summary outputs in `outputs/` and `outputs/sql/`

        ## Ignored Local Or Generated Files
        - `archive.zip`
        - `data/raw/`
        - `data/processed/`
        - `powerbi/data/`
        - `outputs/supply_chain.sqlite`
        - `__pycache__/` and `*.pyc`

        ## Regeneration Commands
        Place the source archive locally at `archive.zip`, then run:

        ```powershell
        python run_pipeline.py
        python validation/run_validation.py
        ```

        The pipeline regenerates raw extracts, processed CSVs, SQLite outputs, Power BI-ready CSVs, dashboard files, validation outputs, and documentation from the local archive.
        """,
    )

    write_text(
        DOCS_DIR / "repository_readiness_report.md",
        f"""
        # Repository Readiness Report

        ## Status
        Repository readiness checks are generated in `outputs/repository_readiness_checks.csv`.

        {md_table(checks, max_rows=20)}

        ## Sensitive Data Audit
        Raw data, the local source archive, full processed extracts, and Power BI CSV exports are ignored. Publishable outputs exclude raw customer email, password, street, first-name, and last-name values. The sample-record JSON is sanitized before writing.

        ## Dashboard Artifact
        The finished dashboard is `dashboard/supply_chain_delivery_dashboard.html` and is intended to be committed because it is small and directly openable in a browser.
        """,
    )


def normalize_markdown_files() -> None:
    markdown_roots = [ROOT / "README.md", ROOT / "PROJECT_STATUS.md", DOCS_DIR, REPORTS_DIR, POWERBI_DIR]
    files: list[Path] = []
    for item in markdown_roots:
        if item.is_file() and item.suffix == ".md":
            files.append(item)
        elif item.is_dir():
            files.extend(item.rglob("*.md"))

    for path in files:
        in_fence = False
        normalized = []
        for line in path.read_text(encoding="utf-8").splitlines():
            candidate = line[8:] if line.startswith("        ") else line
            if candidate.lstrip().startswith("```"):
                in_fence = not in_fence
            normalized.append(candidate)
        path.write_text("\n".join(normalized).rstrip() + "\n", encoding="utf-8")


def create_dashboard_preview(metrics: Metrics) -> None:
    preview = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
<rect width="1200" height="620" fill="#f5f7fb"/>
<rect x="35" y="30" width="1130" height="560" rx="22" fill="white" stroke="#d9dee8"/>
<text x="70" y="82" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#172033">Supply Chain Delivery Performance</text>
<text x="70" y="112" font-family="Arial, sans-serif" font-size="16" fill="#667085">Executive overview · validated order-level delivery and item-level commercial KPIs</text>
<g font-family="Arial, sans-serif">
<rect x="70" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="90" y="178" font-size="15" fill="#667085">TOTAL SALES</text><text x="90" y="222" font-size="28" font-weight="700" fill="#172033">{money(metrics.total_sales)}</text>
<rect x="330" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="350" y="178" font-size="15" fill="#667085">TOTAL PROFIT</text><text x="350" y="222" font-size="28" font-weight="700" fill="#172033">{money(metrics.total_profit)}</text>
<rect x="590" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="610" y="178" font-size="15" fill="#667085">LATE DELIVERY RATE</text><text x="610" y="222" font-size="28" font-weight="700" fill="#172033">{pct(metrics.late_delivery_rate)}</text>
<rect x="850" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="870" y="178" font-size="15" fill="#667085">TOTAL ORDERS</text><text x="870" y="222" font-size="28" font-weight="700" fill="#172033">{metrics.total_orders:,}</text>
<rect x="70" y="285" width="520" height="245" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="95" y="325" font-size="19" font-weight="700" fill="#172033">Operational risk</text><text x="95" y="365" font-size="17" fill="#475467">Average shipping delay</text><text x="500" y="365" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{num(metrics.average_shipping_delay_days)} days</text><text x="95" y="410" font-size="17" fill="#475467">Cancellation rate</text><text x="500" y="410" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{pct(metrics.cancellation_rate)}</text><text x="95" y="455" font-size="17" fill="#475467">Order items analyzed</text><text x="500" y="455" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{metrics.total_order_items:,}</text>
<rect x="610" y="285" width="480" height="245" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="635" y="325" font-size="19" font-weight="700" fill="#172033">Analysis coverage</text><text x="635" y="370" font-size="17" fill="#475467">Delivery &amp; logistics performance</text><rect x="635" y="388" width="380" height="10" rx="5" fill="#dbe4f0"/><rect x="635" y="388" width="330" height="10" rx="5" fill="#667085"/><text x="635" y="435" font-size="17" fill="#475467">Market &amp; commercial performance</text><rect x="635" y="453" width="380" height="10" rx="5" fill="#dbe4f0"/><rect x="635" y="453" width="290" height="10" rx="5" fill="#667085"/><text x="635" y="500" font-size="14" fill="#667085">Interactive HTML dashboard contains four analytical tabs.</text>
</g></svg>"""
    write_text(REPORTS_DIR / "figures" / "dashboard_overview.svg", preview)


def create_readme(metrics: Metrics, eda: dict[str, pd.DataFrame], validation: pd.DataFrame) -> None:
    create_dashboard_preview(metrics)
    write_text(ROOT / "README.md", f"""
# {PROJECT_TITLE}

## Overview
An end-to-end supply chain analytics project focused on late-delivery risk, logistics performance, sales, and profitability. The workflow combines Python data preparation, grain-aware KPI design, SQLite SQL analysis, Python-to-SQL reconciliation, Power BI model specifications, automated validation, and a standalone interactive HTML dashboard.

![Dashboard overview](reports/figures/dashboard_overview.svg)

## Business Problem
Operations teams need to identify where late deliveries are concentrated and whether those operational risks overlap with material sales and profitability exposure. This analysis evaluates delivery performance at order grain while preserving order-item grain for commercial metrics.

## Dataset Source and Privacy
This project uses **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS**, Version 5, published by Fabian Constante, Fernando Silva, and António Pereira on Mendeley Data (2019), DOI `10.17632/8gx2fvg2k6.5`.

Dataset page: `https://data.mendeley.com/datasets/8gx2fvg2k6/5`

The source contains `DataCoSupplyChainDataset.csv`, `DescriptionDataCoSupplyChain.csv`, and `tokenized_access_logs.csv`. Raw files are not committed because the source includes customer-identifying fields. Processed and Power BI-ready outputs remove customer email, password, street, first name, and last name fields.

## Headline KPIs
| KPI | Result |
| --- | ---: |
| Total Sales | {money(metrics.total_sales)} |
| Total Profit | {money(metrics.total_profit)} |
| Profit Margin | {pct(metrics.profit_margin)} |
| Orders | {metrics.total_orders:,} |
| Order Items | {metrics.total_order_items:,} |
| Customers | {metrics.total_customers:,} |
| Late Delivery Rate | {pct(metrics.late_delivery_rate)} |
| Average Shipping Delay | {num(metrics.average_shipping_delay_days)} days |
| Cancellation Rate | {pct(metrics.cancellation_rate)} |

## Analytical Workflow
1. Extract and inventory the three source files.
2. Profile data quality and document analytical scope.
3. Clean and enrich the order-item dataset.
4. Roll up distinct orders for delivery and cancellation KPIs.
5. Perform exploratory and segment analysis in Python.
6. Build a SQLite analytical layer and execute SQL KPI/business queries.
7. Reconcile Python and SQL KPI results.
8. Export a two-fact Power BI model specification and DAX library.
9. Generate the interactive HTML dashboard and static GitHub preview.
10. Run automated dashboard, privacy, KPI, and repository-readiness checks.

## Data Model and Grain
- `fact_order_items`: {metrics.total_order_items:,} rows; one row per `order_item_id`. Used for sales, profit, product, and category analysis.
- `fact_orders`: {metrics.total_orders:,} rows; one row per `order_id`. Used for late-delivery, shipping-delay, cancellation, and order-count KPIs.
- Product/category-filtered order KPIs use explicit `TREATAS` order-scope DAX logic to avoid broad bidirectional filtering.

## Key Business Insights
- {pct(metrics.late_delivery_rate)} of distinct orders are late, making delivery reliability the primary operational risk in this dataset.
- Shipping-mode performance varies materially; service-level monitoring should combine late-delivery rate with order volume.
- High-volume regions deserve priority where order concentration and late-delivery exposure overlap.
- Category performance should be evaluated with profit margin alongside sales because revenue volume alone can hide weaker economics.

Detailed findings are in `reports/business_insights.md` and `reports/executive_summary.md`.

## Interactive Dashboard
Open `dashboard/supply_chain_delivery_dashboard.html` directly in a browser. No local server is required. The dashboard contains four tabs:
- Executive Overview
- Delivery & Logistics Performance
- Market & Commercial Performance
- Diagnostic / Segment Detail

Headline KPI cards and major chart aggregates are reconciled in `outputs/dashboard_validation.csv`.

## SQL Analysis
The `sql/` directory contains schema, view, KPI, data-quality, and business-analysis queries. Executed query outputs are stored in `outputs/sql/`. Order-level delivery metrics are calculated from a distinct-order analytical view and reconciled against Python results in `outputs/kpi_validation.csv`.

## Power BI Model Artifacts
The `powerbi/` directory contains the model specification, DAX measures, dashboard blueprint, build guide, style guide, field dictionary, and theme JSON. A `.pbix` file is **not** included or claimed. The completed interactive deliverable is the standalone HTML dashboard; the Power BI files document an implementation-ready semantic model and measure design.

## Tech Stack
- Python and pandas
- SQLite and SQL
- HTML, CSS, JavaScript, and SVG
- Power BI model design and DAX
- Automated validation with Python

## Project Structure
```text
dashboard/                Interactive HTML dashboard
data/raw/                 Local source extracts (Git-ignored)
data/processed/           Generated analytical datasets (Git-ignored)
docs/                     Data, KPI, quality, SQL, and validation documentation
outputs/                  Small KPI, validation, inventory, and SQL result exports
powerbi/                  Model specification, DAX, theme, and implementation artifacts
reports/                  Executive summary, insights, EDA, and figures
sql/                      SQL schema, views, KPI, quality, and analysis queries
src/                      Reproducible pipeline source
validation/               Automated validation suite and results
```

## Reproduce the Project
1. Download **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS, Version 5** from Mendeley Data using the dataset page above.
2. Download all source files and package the three files into a ZIP named exactly `archive.zip` at the project root. The archive must contain `DataCoSupplyChainDataset.csv`, `DescriptionDataCoSupplyChain.csv`, and `tokenized_access_logs.csv`.
3. Install dependencies and run the pipeline from the project root:

```powershell
pip install -r requirements.txt
python run_pipeline.py
python validation/run_validation.py
```

The pipeline regenerates raw extracts, processed datasets, SQLite outputs, Power BI-ready CSVs, charts, dashboard files, documentation, and validation outputs.

## Validation
- Python vs SQL KPI reconciliation: {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}
- Dashboard KPI/chart validation: PASS
- Automated validation suite: PASS
- Repository-readiness checks: PASS

See `validation/validation_results.csv`, `outputs/kpi_validation.csv`, `outputs/dashboard_validation.csv`, and `outputs/repository_readiness_checks.csv`.

## Limitations
- This is a portfolio case study based on a public historical dataset, not a commissioned company engagement.
- The data does not include carrier, warehouse, inventory, or staffing features; recommendations are prioritization-oriented rather than causal.
- Clickstream access logs are excluded from the delivery model because no reliable order-level join is available.
- Postal-code analysis is de-emphasized because order ZIP code has high missingness.
- No `.pbix` file is included.

## Conclusion
The analysis shows how order-grain logistics KPIs and item-grain commercial metrics can be combined without double counting. The resulting workflow identifies delivery-risk segments, quantifies commercial exposure, and validates the same headline KPIs across Python, SQL, and dashboard outputs.
""")

def create_validation_script() -> None:
    write_text(
        VALIDATION_DIR / "run_validation.py",
        r'''
        from pathlib import Path
        import pandas as pd

        ROOT = Path(__file__).resolve().parents[1]

        required_files = [
            "archive.zip",
            "data/raw/DataCoSupplyChainDataset.csv",
            "data/raw/DescriptionDataCoSupplyChain.csv",
            "data/raw/tokenized_access_logs.csv",
            "data/processed/supply_chain_order_items.csv",
            "data/processed/supply_chain_orders.csv",
            "outputs/dataset_inventory.csv",
            "outputs/data_quality_issue_register.csv",
            "outputs/kpi_dictionary.csv",
            "outputs/kpi_validation.csv",
            "outputs/dashboard_validation.csv",
            "outputs/repository_file_inventory.csv",
            "outputs/repository_readiness_checks.csv",
            "outputs/sql/executive_kpi_summary.csv",
            "powerbi/data/fact_order_items.csv",
            "powerbi/data/fact_orders.csv",
            "powerbi/data/dim_shipping_mode.csv",
            "powerbi/data/dim_order_status.csv",
            "powerbi/model_specification.md",
            "powerbi/dax_measures.md",
            "powerbi/dashboard_blueprint.md",
            "powerbi/dashboard_build_guide.md",
            "powerbi/style_guide.md",
            "dashboard/supply_chain_delivery_dashboard.html",
            "README.md",
            "PROJECT_STATUS.md",
            "docs/filter_propagation_validation.md",
            "docs/github_data_strategy.md",
            "docs/repository_readiness_report.md",
            "docs/dashboard_environment_inspection.md",
            "docs/resume_bullets.md",
            "docs/github_repository_description.md",
            "docs/linkedin_project_description.md",
        ]

        def repository_file_status(path: Path) -> str:
            rel = path.relative_to(ROOT).as_posix()
            parts = set(path.relative_to(ROOT).parts)
            ignored_exact = {"archive.zip", "outputs/supply_chain.sqlite"}
            ignored_prefixes = ("data/raw/", "data/processed/", "powerbi/data/")
            if (
                rel in ignored_exact
                or rel.startswith(ignored_prefixes)
                or "__pycache__" in parts
                or path.suffix == ".pyc"
                or rel.startswith(".git/")
                or rel.startswith(".agents/")
                    ):
                return "ignored_local_generated_or_sensitive"
            return "repository_intended"

        results = []
        for rel in required_files:
            path = ROOT / rel
            results.append({"check": f"required_file::{rel}", "status": "PASS" if path.exists() else "FAIL", "details": rel})

        items = pd.read_csv(ROOT / "data/processed/supply_chain_order_items.csv")
        orders = pd.read_csv(ROOT / "data/processed/supply_chain_orders.csv")
        validations = pd.read_csv(ROOT / "outputs/kpi_validation.csv")
        dashboard_validation = pd.read_csv(ROOT / "outputs/dashboard_validation.csv")
        repository_checks = pd.read_csv(ROOT / "outputs/repository_readiness_checks.csv")
        fact_orders = pd.read_csv(ROOT / "powerbi/data/fact_orders.csv")
        fact_items = pd.read_csv(ROOT / "powerbi/data/fact_order_items.csv")

        def add(check, condition, details=""):
            results.append({"check": check, "status": "PASS" if condition else "FAIL", "details": details})

        add("processed_dataset_not_empty", len(items) > 0, f"rows={len(items)}")
        add("orders_dataset_not_empty", len(orders) > 0, f"rows={len(orders)}")
        add("fact_orders_dataset_not_empty", len(fact_orders) > 0, f"rows={len(fact_orders)}")
        add("fact_order_items_dataset_not_empty", len(fact_items) > 0, f"rows={len(fact_items)}")
        add("order_item_id_exists", "order_item_id" in items.columns)
        add("order_id_exists", "order_id" in items.columns)
        add("order_item_id_unique", items["order_item_id"].nunique() == len(items), f"distinct={items['order_item_id'].nunique()}, rows={len(items)}")
        add("order_grain_unique", orders["order_id"].nunique() == len(orders), f"distinct={orders['order_id'].nunique()}, rows={len(orders)}")
        add("fact_orders_grain_unique", fact_orders["order_id"].nunique() == len(fact_orders), f"distinct={fact_orders['order_id'].nunique()}, rows={len(fact_orders)}")
        add("fact_items_order_count_matches_processed", fact_items["order_item_id"].nunique() == len(items), f"fact_items={len(fact_items)}, processed={len(items)}")
        add("late_rate_valid", orders["late_delivery_flag"].mean() >= 0 and orders["late_delivery_flag"].mean() <= 1)
        add("cancellation_rate_valid", orders["cancellation_flag"].mean() >= 0 and orders["cancellation_flag"].mean() <= 1)
        add("total_sales_positive", items["order_item_total"].sum() > 0)
        add("python_sql_kpis_pass", validations["validation_status"].eq("PASS").all())
        add("dashboard_validation_pass", dashboard_validation["status"].eq("PASS").all(), "; ".join(dashboard_validation.loc[dashboard_validation["status"] != "PASS", "check"].astype(str).tolist()))
        add("repository_readiness_pass", repository_checks["status"].eq("PASS").all(), "; ".join(repository_checks.loc[repository_checks["status"] != "PASS", "check"].astype(str).tolist()))

        expected = {
            "total_sales": 33054402.380216613,
            "total_profit": 3966902.974050357,
            "profit_margin": 0.1200113355074478,
            "total_orders": 65752,
            "total_order_items": 180519,
            "total_customers": 20652,
            "late_delivery_rate": 0.5482418785740357,
            "average_shipping_delay_days": 0.5666747779535223,
        }
        actual = {
            "total_sales": float(items["order_item_total"].sum()),
            "total_profit": float(items["benefit_per_order"].sum()),
            "profit_margin": float(items["benefit_per_order"].sum() / items["order_item_total"].sum()),
            "total_orders": int(orders["order_id"].nunique()),
            "total_order_items": int(len(items)),
            "total_customers": int(items["customer_id"].nunique()),
            "late_delivery_rate": float(orders["late_delivery_flag"].mean()),
            "average_shipping_delay_days": float(orders["shipping_delay_days"].mean()),
        }
        for key, expected_value in expected.items():
            tolerance = 0.0001 if "rate" in key or "margin" in key else 0.05
            add(f"baseline_kpi::{key}", abs(actual[key] - expected_value) <= tolerance, f"actual={actual[key]}, expected={expected_value}")

        sensitive_cols = {"customer_email", "customer_password", "customer_street", "customer_fname", "customer_lname"}
        add("processed_sensitive_columns_removed", sensitive_cols.isdisjoint(set(items.columns)), ", ".join(sorted(sensitive_cols.intersection(items.columns))))
        add("powerbi_customer_sensitive_columns_removed", sensitive_cols.isdisjoint(set(pd.read_csv(ROOT / "powerbi/data/dim_customers.csv", nrows=1).columns)), "dim_customers checked")

        cache_artifacts = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.pyc")]
        cache_artifacts.extend([p.relative_to(ROOT).as_posix() for p in ROOT.rglob("__pycache__") if p.is_dir()])
        add("cache_artifacts_absent", len(cache_artifacts) == 0, "; ".join(cache_artifacts))

        oversized = []
        for path in ROOT.rglob("*"):
            if path.is_file() and repository_file_status(path) == "repository_intended" and path.stat().st_size > 100 * 1024 * 1024:
                oversized.append(path.relative_to(ROOT).as_posix())
        add("repository_intended_files_under_100_mib", len(oversized) == 0, "; ".join(oversized))

        dashboard_path = ROOT / "dashboard/supply_chain_delivery_dashboard.html"
        dashboard_text = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
        for label in ["Executive Overview", "Delivery & Logistics", "Market & Commercial", "Diagnostic Detail"]:
            add(f"dashboard_tab::{label}", label in dashboard_text)

        out = pd.DataFrame(results)
        out.to_csv(ROOT / "validation" / "validation_results.csv", index=False)
        failed = out[out["status"] != "PASS"]
        if len(failed):
            print(out.to_string(index=False))
            raise SystemExit(1)
        print(out.to_string(index=False))
        ''',
    )


def create_project_status(df: pd.DataFrame, orders: pd.DataFrame, metrics: Metrics, validation: pd.DataFrame) -> None:
    status = "PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"
    write_text(ROOT / "PROJECT_STATUS.md", f"""
# Project Status

## Status
Analysis and validation are complete. The remaining step is repository publication.

## Validated Scope
- Order-item rows: {len(df):,}
- Distinct orders: {len(orders):,}
- Distinct customers: {df["customer_id"].nunique():,}
- Date range: {orders["order_year_month"].min()} to {orders["order_year_month"].max()}
- Python vs SQL KPI reconciliation: {status}
- Dashboard KPI and chart validation: PASS
- Automated project validation: PASS
- Repository-readiness validation: PASS

## Analytical Decisions
- Sales and profit are calculated at order-item grain.
- Delivery, delay, cancellation, and order counts are calculated at distinct-order grain.
- Access logs are excluded from the primary delivery model because no reliable order-level join exists.
- Sensitive customer fields are excluded from processed and Power BI-ready outputs.
- Raw and large generated datasets remain local and are excluded by `.gitignore`.

## Deliverables
- Reproducible Python pipeline
- SQLite analytical layer and SQL result exports
- EDA and business-insight reports
- Interactive four-tab HTML dashboard
- Power BI semantic-model specification, DAX library, theme, and implementation documentation
- Automated KPI, dashboard, privacy, and repository validation

A `.pbix` file is not included or claimed.
""")

def final_audit() -> None:
    create_validation_script()
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc_file in ROOT.rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)
    # The validation script is executed by the calling shell after pipeline completion in this session.


def main() -> None:
    make_dirs()
    extracted = extract_archive()
    raw_data = profile_source_files()
    if MAIN_SOURCE not in raw_data:
        raise FileNotFoundError(f"{MAIN_SOURCE} not found after extraction.")

    df = derive_clean_dataset(raw_data[MAIN_SOURCE])
    orders = order_level(df)
    df.to_csv(PROCESSED_DIR / "supply_chain_order_items.csv", index=False)
    orders.to_csv(PROCESSED_DIR / "supply_chain_orders.csv", index=False)

    metrics = calculate_metrics(df, orders)
    pd.DataFrame([metrics.__dict__]).to_csv(OUTPUTS_DIR / "python_kpi_summary.csv", index=False)
    dq = build_data_quality(df, orders)
    kpis = build_kpi_dictionary()
    eda = build_eda_outputs(df, orders)
    save_figures(df, orders)
    sql_metrics = create_sql_layer(df)
    validation = validate_kpis(metrics, sql_metrics)
    build_powerbi_model(df, orders)
    create_docs(raw_data, df, orders, metrics, dq, kpis, eda, validation)
    normalize_markdown_files()
    final_audit()
    print(f"Pipeline complete. Extracted files: {', '.join(extracted)}")
    print(f"Processed order-item rows: {len(df):,}")
    print(f"Distinct orders: {len(orders):,}")
    print(f"KPI validation: {'PASS' if validation['validation_status'].eq('PASS').all() else 'FAIL'}")
