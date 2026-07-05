# Grain Analysis

## Main Dataset Grain
The main analytical dataset is **one row per order item**.

Evidence:
- Rows: 180,519
- Distinct `order_item_id`: 180,519
- Duplicate `order_item_id` count: 0
- Distinct `order_id`: 65,752
- Order IDs with multiple rows: 45,902

## KPI Grain Governance
- Sales, discounts, quantities, and item profit are summed at order-item grain.
- Orders, late deliveries, shipping duration, cancellation rate, and average delay are calculated from an order-level table to prevent double counting.
- Customer and product counts use distinct identifiers.
