from __future__ import annotations

import sqlite3

import pandas as pd

from .common import OUTPUTS_DIR, SQL_DIR, SQL_OUTPUTS_DIR, write_text

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
