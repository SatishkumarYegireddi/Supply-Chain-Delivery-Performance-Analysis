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
