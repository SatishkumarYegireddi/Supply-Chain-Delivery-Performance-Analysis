from __future__ import annotations

import math

import pandas as pd

from src import metrics as metrics_module
from src.data_preparation import derive_clean_dataset, order_level
from src.metrics import Metrics, calculate_metrics, validate_kpis


def raw_order_items() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Order Id": 1001,
                "Order Item Id": 1,
                "Order Date (DateOrders)": "2024-01-01 08:00:00",
                "shipping date (DateOrders)": "2024-01-04 08:00:00",
                "Days for shipping (real)": 3,
                "Days for shipment (scheduled)": 2,
                "Late_delivery_risk": 1,
                "Order Status": "COMPLETE",
                "Sales": 120.0,
                "Order Item Total": 100.0,
                "Order Item Discount": 20.0,
                "Benefit per order": 12.0,
                "Customer Id": 501,
                "Shipping Mode": "First Class",
                "Type": "DEBIT",
                "Market": "Europe",
                "Order Region": "Western Europe",
                "Order Country": "France",
                "Order State": "Ile-de-France",
                "Order City": "Paris",
                "Customer Segment": "Consumer",
                "Delivery Status": "Late delivery",
                "Department Name": "Fitness",
                "Category Name": "Cycling",
                "Customer Email": "customer@example.com",
                "Customer Password": "secret",
                "Customer Street": "1 Main St",
                "Customer Fname": "Ada",
                "Customer Lname": "Lovelace",
                "Product Image": "image.jpg",
                "Product Description": "description",
            },
            {
                "Order Id": 1001,
                "Order Item Id": 2,
                "Order Date (DateOrders)": "2024-01-01 08:00:00",
                "shipping date (DateOrders)": "2024-01-04 08:00:00",
                "Days for shipping (real)": 3,
                "Days for shipment (scheduled)": 2,
                "Late_delivery_risk": 1,
                "Order Status": "COMPLETE",
                "Sales": 80.0,
                "Order Item Total": 70.0,
                "Order Item Discount": 10.0,
                "Benefit per order": -5.0,
                "Customer Id": 501,
                "Shipping Mode": "First Class",
                "Type": "DEBIT",
                "Market": "Europe",
                "Order Region": "Western Europe",
                "Order Country": "France",
                "Order State": "Ile-de-France",
                "Order City": "Paris",
                "Customer Segment": "Consumer",
                "Delivery Status": "Late delivery",
                "Department Name": "Fitness",
                "Category Name": "Cycling",
            },
            {
                "Order Id": 1002,
                "Order Item Id": 3,
                "Order Date (DateOrders)": "2024-01-02 09:30:00",
                "shipping date (DateOrders)": "2024-01-02 09:30:00",
                "Days for shipping (real)": 0,
                "Days for shipment (scheduled)": 1,
                "Late_delivery_risk": 0,
                "Order Status": "CANCELED",
                "Sales": 50.0,
                "Order Item Total": 40.0,
                "Order Item Discount": 10.0,
                "Benefit per order": 4.0,
                "Customer Id": 502,
                "Shipping Mode": "Standard Class",
                "Type": "TRANSFER",
                "Market": "LATAM",
                "Order Region": "South America",
                "Order Country": "Brazil",
                "Order State": "Sao Paulo",
                "Order City": "Sao Paulo",
                "Customer Segment": "Corporate",
                "Delivery Status": "Shipping canceled",
                "Department Name": "Outdoors",
                "Category Name": "Camping",
            },
        ]
    )


def test_derive_clean_dataset_calculates_delivery_fields_and_removes_sensitive_columns() -> None:
    cleaned = derive_clean_dataset(raw_order_items())

    first = cleaned.loc[0]
    assert first["shipping_delay_days"] == 1
    assert first["late_delivery_flag"] == 1
    assert first["on_time_flag"] == 0
    assert first["cancellation_flag"] == 0
    assert first["suspected_fraud_flag"] == 0
    assert first["profit_margin"] == 0.12
    assert first["order_year_month"] == "2024-01"
    assert first["delay_severity"] == "1 day late"
    assert first["delivery_performance_group"] == "Late"
    assert first["geography_key"] == "europe_western_europe_france_ile_de_france_paris"

    assert cleaned.loc[2, "shipping_delay_days"] == -1
    assert cleaned.loc[2, "delay_severity"] == "Early"
    assert cleaned.loc[2, "cancellation_flag"] == 1

    removed_columns = {
        "customer_email",
        "customer_password",
        "customer_street",
        "customer_fname",
        "customer_lname",
        "product_image",
        "product_description",
    }
    assert removed_columns.isdisjoint(cleaned.columns)


def test_derive_clean_dataset_classifies_delay_severity_edges() -> None:
    raw = raw_order_items().head(1).copy()
    raw = pd.concat([raw] * 6, ignore_index=True)
    raw["Order Id"] = range(2001, 2007)
    raw["Order Item Id"] = range(11, 17)
    raw["Days for shipping (real)"] = pd.Series([1, 2, 3, 5, 7, math.nan], dtype="float64")
    raw["Days for shipment (scheduled)"] = pd.Series([2, 2, 2, 2, 2, 2], dtype="float64")

    cleaned = derive_clean_dataset(raw)

    assert cleaned["delay_severity"].tolist() == [
        "Early",
        "On schedule",
        "1 day late",
        "2-3 days late",
        "4+ days late",
        "Unknown",
    ]


def test_order_level_rolls_item_rows_to_distinct_orders() -> None:
    cleaned = derive_clean_dataset(raw_order_items())

    orders = order_level(cleaned)

    assert orders["order_id"].tolist() == [1001, 1002]
    order_1001 = orders.loc[orders["order_id"] == 1001].iloc[0]
    assert order_1001["order_item_count"] == 2
    assert order_1001["gross_order_sales"] == 200.0
    assert order_1001["net_order_sales"] == 170.0
    assert order_1001["order_discount"] == 30.0
    assert order_1001["order_profit"] == 7.0
    assert order_1001["late_delivery_flag"] == 1


def test_calculate_metrics_uses_item_grain_for_sales_and_order_grain_for_delivery_rates() -> None:
    cleaned = derive_clean_dataset(raw_order_items())
    orders = order_level(cleaned)

    metrics = calculate_metrics(cleaned, orders)

    assert metrics.total_sales == 210.0
    assert metrics.gross_sales == 250.0
    assert metrics.total_profit == 11.0
    assert metrics.total_orders == 2
    assert metrics.total_order_items == 3
    assert metrics.total_customers == 2
    assert metrics.average_order_value == 105.0
    assert metrics.late_deliveries == 1
    assert metrics.late_delivery_rate == 0.5
    assert metrics.on_time_deliveries == 1
    assert metrics.on_time_delivery_rate == 0.5
    assert metrics.cancelled_orders == 1
    assert metrics.cancellation_rate == 0.5
    assert metrics.average_shipping_delay_days == 0.0
    assert metrics.average_actual_shipping_days == 1.5
    assert metrics.average_scheduled_shipping_days == 1.5


def test_calculate_metrics_returns_nan_ratios_when_no_orders() -> None:
    item_columns = ["order_item_total", "sales", "benefit_per_order", "customer_id"]
    order_columns = [
        "order_id",
        "late_delivery_flag",
        "cancellation_flag",
        "shipping_delay_days",
        "days_for_shipping_real",
        "days_for_shipment_scheduled",
    ]
    metrics = calculate_metrics(pd.DataFrame(columns=item_columns), pd.DataFrame(columns=order_columns))

    assert metrics.total_orders == 0
    assert metrics.total_order_items == 0
    assert math.isnan(metrics.profit_margin)
    assert math.isnan(metrics.average_order_value)
    assert math.isnan(metrics.late_delivery_rate)
    assert math.isnan(metrics.on_time_delivery_rate)
    assert math.isnan(metrics.cancellation_rate)
    assert math.isnan(metrics.average_shipping_delay_days)


def test_validate_kpis_applies_rate_and_value_tolerances(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(metrics_module, "OUTPUTS_DIR", tmp_path)
    metrics = Metrics(
        total_sales=100.0,
        gross_sales=120.0,
        total_profit=10.0,
        profit_margin=0.1,
        total_orders=2,
        total_order_items=3,
        total_customers=2,
        average_order_value=50.0,
        late_deliveries=1,
        late_delivery_rate=0.5,
        on_time_deliveries=1,
        on_time_delivery_rate=0.5,
        cancelled_orders=0,
        cancellation_rate=0.0,
        average_shipping_delay_days=1.0,
        average_actual_shipping_days=3.0,
        average_scheduled_shipping_days=2.0,
    )
    sql_metrics = {
        "total_sales": 100.009,
        "gross_sales": 120.0,
        "total_profit": 10.0,
        "profit_margin": 0.10009,
        "total_orders": 2,
        "total_order_items": 3,
        "total_customers": 2,
        "average_order_value": 50.0,
        "late_delivery_rate": 0.5002,
        "on_time_delivery_rate": 0.5,
        "cancellation_rate": 0.0,
        "average_shipping_delay_days": 1.02,
    }

    validation = validate_kpis(metrics, sql_metrics)

    statuses = dict(zip(validation["kpi"], validation["validation_status"], strict=True))
    assert statuses["total_sales"] == "PASS"
    assert statuses["profit_margin"] == "PASS"
    assert statuses["late_delivery_rate"] == "FAIL"
    assert statuses["average_shipping_delay_days"] == "FAIL"
    assert (tmp_path / "kpi_validation.csv").exists()
