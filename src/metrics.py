from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .common import OUTPUTS_DIR

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
