-- Supply Chain Delivery Performance Analysis
-- SQLite analytical schema
--
-- Source dataset:
-- data/processed/supply_chain_order_items.csv
--
-- Grain:
-- One row per order item.
--
-- The order_items table stores the cleaned and feature-engineered
-- analytical dataset used by the SQL queries and reporting layer.

DROP TABLE IF EXISTS order_items;

CREATE TABLE order_items (
    type TEXT,
    days_for_shipping_real INTEGER,
    days_for_shipment_scheduled INTEGER,
    benefit_per_order REAL,
    sales_per_customer REAL,
    delivery_status TEXT,
    late_delivery_risk INTEGER,
    category_id INTEGER,
    category_name TEXT,
    customer_city TEXT,
    customer_country TEXT,
    customer_id INTEGER,
    customer_segment TEXT,
    customer_state TEXT,
    customer_zipcode REAL,
    department_id INTEGER,
    department_name TEXT,
    latitude REAL,
    longitude REAL,
    market TEXT,
    order_city TEXT,
    order_country TEXT,
    order_customer_id INTEGER,
    order_date_dateorders TEXT,
    order_id INTEGER,
    order_item_cardprod_id INTEGER,
    order_item_discount REAL,
    order_item_discount_rate REAL,
    order_item_id INTEGER,
    order_item_product_price REAL,
    order_item_profit_ratio REAL,
    order_item_quantity INTEGER,
    sales REAL,
    order_item_total REAL,
    order_profit_per_order REAL,
    order_region TEXT,
    order_state TEXT,
    order_status TEXT,
    order_zipcode REAL,
    product_card_id INTEGER,
    product_category_id INTEGER,
    product_name TEXT,
    product_price REAL,
    product_status INTEGER,
    shipping_date_dateorders TEXT,
    shipping_mode TEXT,
    order_date TEXT,
    shipping_date TEXT,
    shipping_delay_days INTEGER,
    late_delivery_flag INTEGER,
    on_time_flag INTEGER,
    cancellation_flag INTEGER,
    suspected_fraud_flag INTEGER,
    profit_margin REAL,
    order_year INTEGER,
    order_quarter TEXT,
    order_month INTEGER,
    order_year_month TEXT,
    order_weekday TEXT,
    order_date_key INTEGER,
    shipping_date_key INTEGER,
    delay_severity TEXT,
    delivery_performance_group TEXT,
    geography_key TEXT
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items(order_id);

CREATE INDEX IF NOT EXISTS idx_order_items_order_date
    ON order_items(order_date);

CREATE INDEX IF NOT EXISTS idx_order_items_market
    ON order_items(market);

CREATE INDEX IF NOT EXISTS idx_order_items_order_region
    ON order_items(order_region);

CREATE INDEX IF NOT EXISTS idx_order_items_shipping_mode
    ON order_items(shipping_mode);

CREATE INDEX IF NOT EXISTS idx_order_items_category
    ON order_items(category_name);