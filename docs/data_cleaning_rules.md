# Data Cleaning Rules

## Applied Rules
- Extracted raw files from `archive.zip` into `data/raw` without modifying the archive or raw CSVs.
- Standardized column names to snake_case.
- Trimmed whitespace from text fields.
- Parsed order and shipping timestamps into datetime fields.
- Removed sensitive or low-value publication fields from processed outputs: customer email, password, street, first name, last name, product image, and empty product description.
- Created order date attributes: year, quarter, month, year-month, weekday, and date keys.
- Created delivery fields: `shipping_delay_days`, `late_delivery_flag`, `on_time_flag`, `delay_severity`, and `delivery_performance_group`.
- Created order status flags: `cancellation_flag` and `suspected_fraud_flag`.
- Created `profit_margin` using item profit divided by discount-adjusted item total.
- Created a composite `geography_key` for Power BI relationships.

## Row Count Validation
- Source main rows: 180,519
- Processed rows: 180,519
- Rows removed: 0

No analytical rows were deleted.
