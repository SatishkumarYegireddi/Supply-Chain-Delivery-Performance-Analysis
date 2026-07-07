from __future__ import annotations

import pandas as pd

from .common import slug

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: slug(col) for col in df.columns}
    result = df.rename(columns=renamed).copy()
    text_columns = [
        col
        for col in result.columns
        if pd.api.types.is_object_dtype(result[col].dtype)
        or pd.api.types.is_string_dtype(result[col].dtype)
    ]
    for col in text_columns:
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
