# Data Quality Report

## Summary
A reproducible data quality audit was executed against the processed analytical dataset. The audit checks missing values, duplicate rows, key uniqueness, invalid dates, impossible date relationships, negative and non-positive numeric values, discount anomalies, and delivery flag consistency.

## Issue Register
Full issue register: `outputs/data_quality_issue_register.csv`

| issue_id | severity | affected_fields | affected_row_count | affected_pct | status |
| --- | --- | --- | --- | --- | --- |
| DQ001 | Low | product_description | 180519 | 1.00 | Resolved |
| DQ002 | Medium | order_zipcode | 155679 | 0.8624 | Accepted limitation |
| DQ003 | High | customer_email, customer_password, customer_street, customer_fname, customer_lname | 180519 | 1.00 | Resolved |
| DQ004 | Low | all fields | 0 | 0.0000 | Checked |
| DQ005 | High | order_item_id | 0 | 0.0000 | Checked |
| DQ006 | Informational | order_id | 114767 | 0.6358 | Governed |
| DQ007 | Informational | benefit_per_order, order_profit_per_order | 33784 | 0.1871 | Accepted business signal |
| DQ008 | High | order_date, shipping_date | 0 | 0.0000 | Checked |
| DQ009 | Medium | late_delivery_risk, shipping_delay_days | 4423 | 0.0245 | Documented |
| DQ010 | Medium | order_item_discount_rate | 0 | 0.0000 | Checked |
| DQ011 | Medium | sales, order_item_total | 0 | 0.0000 | Checked |
| DQ012 | High | order_date, shipping_date | 0 | 0.0000 | Checked |

## Material Findings
- The dataset is order-item grain, so duplicate `order_id` values are expected and governed through order-level KPI logic.
- Sensitive raw customer fields were excluded from processed and Power BI-ready files.
- Negative profit values were retained as valid loss-making business records.
- Postal-code analysis was deferred because order zipcode missingness limits reliability.
