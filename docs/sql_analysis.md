# SQL Analysis

## SQL Engine
SQLite is used for reproducibility. The local database is generated at `outputs/supply_chain.sqlite`.

## Analytical Model
- `order_items`: one row per order item, loaded from `data/processed/supply_chain_order_items.csv`.
- `v_order_level`: SQL view rolling item rows to one row per order for delivery and cancellation metrics.

## SQL Files
- `sql/schema.sql`
- `sql/views.sql`
- `sql/kpi_queries.sql`
- `sql/business_analysis.sql`
- `sql/validation_queries.sql`

## Executed Analyses
SQL outputs are exported under `outputs/sql`.

Key analyses include executive KPI summary, shipping mode performance, market delivery performance, high-delay regions with minimum volume thresholds, monthly delivery trend, category sales and profitability, order status distribution, top products, and loss-making segments.

## Major SQL Findings
- Total net sales: $33,054,402.4
- Total profit: $3,966,903.0
- Profit margin: 12.0%
- Late delivery rate: 54.8%
- Average shipping delay: 0.6 days
