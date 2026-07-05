-- Executive KPI query
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
