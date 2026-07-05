-- shipping_mode_performance
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

-- market_delivery_performance
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

-- region_high_delay_segments
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

-- monthly_delivery_trend
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

-- category_sales_profit
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

-- high_sales_low_profit_categories
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

-- order_status_distribution
SELECT
                order_status,
                COUNT(*) AS total_orders,
                SUM(net_order_sales) AS total_sales,
                AVG(late_delivery_flag * 1.0) AS late_delivery_rate
            FROM v_order_level
            GROUP BY order_status
            ORDER BY total_orders DESC;

-- top_products_sales_profit
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

-- loss_making_segments
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
