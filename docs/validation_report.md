# Validation Report

## Python vs SQL KPI Reconciliation
Validation output: `outputs/kpi_validation.csv`

| kpi | python_value | sql_value | absolute_difference | tolerance | validation_status |
| --- | --- | --- | --- | --- | --- |
| total_sales | 33,054,402.38 | 33,054,402.38 | 0.0000 | 0.0100 | PASS |
| gross_sales | 36,784,735.01 | 36,784,735.01 | 0.0000 | 0.0100 | PASS |
| total_profit | 3,966,902.97 | 3,966,902.97 | 0.0000 | 0.0100 | PASS |
| profit_margin | 0.1200 | 0.1200 | 0.0000 | 0.0001 | PASS |
| total_orders | 65,752.00 | 65,752.00 | 0.0000 | 0.0100 | PASS |
| total_order_items | 180,519.00 | 180,519.00 | 0.0000 | 0.0100 | PASS |
| total_customers | 20,652.00 | 20,652.00 | 0.0000 | 0.0100 | PASS |
| average_order_value | 502.71 | 502.71 | 0.0000 | 0.0100 | PASS |
| late_delivery_rate | 0.5482 | 0.5482 | 0.0000 | 0.0001 | PASS |
| on_time_delivery_rate | 0.4518 | 0.4518 | 0.0000 | 0.0001 | PASS |
| cancellation_rate | 0.0208 | 0.0208 | 0.0000 | 0.0001 | PASS |
| average_shipping_delay_days | 0.5667 | 0.5667 | 0.0000 | 0.0100 | PASS |

## Status
Critical KPI reconciliation status: PASS

All KPI comparisons use independent Python and SQLite calculations with explicit tolerances.
