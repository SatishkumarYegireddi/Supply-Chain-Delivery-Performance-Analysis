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
