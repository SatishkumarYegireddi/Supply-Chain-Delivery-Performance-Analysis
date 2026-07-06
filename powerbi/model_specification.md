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
