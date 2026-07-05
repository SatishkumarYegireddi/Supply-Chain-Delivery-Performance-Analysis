-- Validation checks used by run_pipeline.py
SELECT COUNT(*) AS order_item_rows FROM order_items;
SELECT COUNT(*) AS order_rows FROM v_order_level;
SELECT COUNT(DISTINCT order_item_id) AS distinct_order_item_ids FROM order_items;
SELECT COUNT(DISTINCT order_id) AS distinct_order_ids FROM order_items;
