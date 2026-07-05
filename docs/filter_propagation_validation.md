# Filter Propagation Validation

## Defect
The prior design documented order-level measures on `dim_orders` while product and geography fields were used in visuals. Single-direction filters from product/geography dimensions through `fact_order_items` could not reliably filter `dim_orders`.

## Corrected Design
The model now uses:
- `fact_orders` for one-row-per-order delivery and cancellation KPIs.
- `fact_order_items` for one-row-per-item commercial KPIs.
- Single-direction dimension-to-fact relationships.
- `TREATAS` in order-level DAX measures so the visible set of `fact_order_items[order_id]` filters `fact_orders`.

## Conceptual Checks
- Market and region fields filter `fact_orders` directly through `dim_geography`, so Total Orders, Late Delivery Rate, Average Shipping Delay, and Cancellation Rate respond to geography filters.
- Category and product fields filter `fact_order_items`; the corrected DAX applies the filtered order IDs to `fact_orders`, so order-level delivery KPIs respond to product/category filters without bidirectional relationships.
- Date filters apply to both facts through `dim_date`, preserving time-series compatibility for sales and delivery KPIs.
- Shipping mode filters apply to `fact_orders`; sales by shipping mode uses the `Shipping-Mode Filtered Sales` measure to push the order scope back to `fact_order_items`.

## KPI Reconciliation
Python and SQL headline KPI validation remains PASS. The corrected DAX uses the same numerator, denominator, and grain definitions as `outputs/kpi_validation.csv`.
