from __future__ import annotations

import json
import re

import pandas as pd

from .common import DOCS_DIR, POWERBI_DATA_DIR, POWERBI_DIR, write_text
from .metrics import Metrics

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

def create_powerbi_docs(metrics: Metrics, eda: dict[str, pd.DataFrame], validation: pd.DataFrame) -> None:
    write_text(
        POWERBI_DIR / "model_specification.md",
        """
        # Power BI Model Specification

        ## Model Design
        The semantic model separates order-level delivery facts from order-item commercial facts. Order-level measures use `fact_orders`, item-level measures use `fact_order_items`, and product/category selections are applied to order-level calculations through explicit order-scope DAX. This keeps filter behavior predictable without bidirectional relationships.

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
    # DAX Measure Library

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

        ## Filter Strategy
        The model uses `fact_orders` for order-grain delivery KPIs and `fact_order_items` for item-grain commercial KPIs. Product and category selections originate from `dim_products` and filter `fact_order_items`; order-level measures then apply the visible item order set to `fact_orders` with `TREATAS`.

        ## Model Structure
        The model now uses:
        - `fact_orders` for one-row-per-order delivery and cancellation KPIs.
        - `fact_order_items` for one-row-per-item commercial KPIs.
        - Single-direction dimension-to-fact relationships.
        - `TREATAS` in order-level DAX measures so the visible set of `fact_order_items[order_id]` filters `fact_orders`.

        ## Conceptual Checks
        - Market and region fields filter `fact_orders` directly through `dim_geography`, so Total Orders, Late Delivery Rate, Average Shipping Delay, and Cancellation Rate respond to geography filters.
        - Category and product fields filter `fact_order_items`; the DAX applies the filtered order IDs to `fact_orders`, so order-level delivery KPIs respond to product/category filters without bidirectional relationships.
        - Date filters apply to both facts through `dim_date`, preserving time-series compatibility for sales and delivery KPIs.
        - Shipping mode filters apply to `fact_orders`; sales by shipping mode uses the `Shipping-Mode Filtered Sales` measure to push the order scope back to `fact_order_items`.

        ## KPI Reconciliation
        Python and SQL headline KPI validation remains {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}. The DAX uses the same numerator, denominator, and grain definitions as `outputs/kpi_validation.csv`.
        """,
    )

    write_text(
        POWERBI_DIR / "dashboard_blueprint.md",
        """
        # Dashboard Blueprint

        ## Page 1: Executive Overview
        Valid measures: Total Sales, Total Profit, Profit Margin, Total Orders, Late Delivery Rate, Average Shipping Delay, Cancellation Rate.
        Visuals use date/geography filters that affect both facts. Shipping-mode sales visuals must use `Shipping-Mode Filtered Sales`.

        ## Page 2: Delivery & Logistics Performance
        Valid measures: Total Orders, Late Deliveries, Late Delivery Rate, Average Actual Shipping Days, Average Scheduled Shipping Days, Average Shipping Delay.
        Dimensions: `dim_shipping_mode`, `dim_geography`, `dim_date`, and order-status fields.

        ## Page 3: Market & Commercial Performance
        Valid measures: Total Sales, Total Profit, Profit Margin, Total Orders, Late Delivery Rate.
        Use `dim_geography` fields for market/region and `dim_products` fields for category/product. Product/category delivery KPIs are valid because DAX measures apply item-filtered order scope to `fact_orders`.

        ## Page 4: Diagnostic / Segment Detail
        Valid matrix fields: market, region, category, product, shipping mode, order status, Total Orders, Total Sales, Total Profit, Profit Margin, Late Delivery Rate, Average Shipping Delay.

        ## Visual Design Guardrails
        No visual should use raw columns from `fact_orders` and `fact_order_items` together without a measure. Product/category delivery visuals must use the scoped order-level measures in `dax_measures.md`.
        """,
    )

    write_text(
        POWERBI_DIR / "dashboard_build_guide.md",
        """
        # Power BI Build Notes

        The completed interactive deliverable is `dashboard/supply_chain_delivery_dashboard.html`. The Power BI directory documents the corresponding model design, DAX measures, theme, and implementation plan.

        If building a Power BI report later, import the CSVs from `powerbi/data`, create the relationships in `model_specification.md`, and create measures from `dax_measures.md`. Keep order-level delivery KPIs on `fact_orders` and commercial KPIs on `fact_order_items`.
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
