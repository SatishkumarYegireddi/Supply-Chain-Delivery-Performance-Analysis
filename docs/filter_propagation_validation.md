# Filter Propagation Validation

## Filter Strategy
The model uses `fact_orders` for order-grain delivery KPIs and `fact_order_items` for item-grain commercial KPIs. Product and category selections originate from `dim_products` and filter `fact_order_items`; order-level measures then apply the visible item order set to `fact_orders` with `TREATAS`.

## Model Structure
The model now uses:
- `fact_orders` for one-row-per-order delivery and cancellation KPIs.
- `fact_order_items` for one-row-per-item commercial KPIs.
- Single-direction dimension-to-fact relationships.
- `TREATAS` in order-level DAX measures so the visible set of `fact_order_items[order_id]` filters `fact_orders`.

## Conceptual Checks
- Market and region fields filter `fact_orders` directly through `dim_geography`, so Total Orders, Late Delivery Rate, Average Shipping Delay, and Cancellation Rate respond to geography filters.
- Category and product fields filter `fact_order_items`; the DAX applies the filtered order IDs to `fact_orders`, so order-level delivery KPIs respond to product/category filters without bidirectional relationships.
- Date filters apply to both facts through `dim_date`, preserving time-series compatibility for sales and delivery KPIs.
- Shipping mode filters apply to `fact_orders`; sales by shipping mode uses the `Shipping-Mode Filtered Sales` measure to push the order scope back to `fact_order_items`.

## KPI Reconciliation
Python and SQL headline KPI validation remains PASS. The DAX uses the same numerator, denominator, and grain definitions as `outputs/kpi_validation.csv`.
