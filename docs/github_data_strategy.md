# GitHub Data Strategy

## Decision
The repository should keep source code, SQL, validation logic, documentation, charts, small summary outputs, Power BI model documentation, and the finished HTML dashboard under version control.

The repository should not commit raw source extracts, processed full-detail datasets, generated Power BI CSV extracts, the generated SQLite database, Python cache artifacts, or the local `archive.zip`.

## Why `archive.zip` Is Ignored
The local archive is 25.67 MiB, which is below GitHub's single-file limit, but it contains the raw source data with customer-identifying fields. Keeping it local avoids publishing raw sensitive fields and avoids duplicating generated extracts. The pipeline remains reproducible when `archive.zip` is present locally at the project root.

## GitHub File-Size Constraint
GitHub blocks normal pushes containing a single file larger than 100 MiB. The generated processed order-item CSV is 102.13 MiB and must remain ignored.

## Current Largest Local Files
| path | size_mb | repository_status |
| --- | --- | --- |
| data/processed/supply_chain_order_items.csv | 102.12 | ignored_local_generated_or_sensitive |
| outputs/supply_chain.sqlite | 100.10 | ignored_local_generated_or_sensitive |
| data/raw/DataCoSupplyChainDataset.csv | 91.47 | ignored_local_generated_or_sensitive |
| data/raw/tokenized_access_logs.csv | 91.03 | ignored_local_generated_or_sensitive |
| powerbi/data/fact_order_items.csv | 30.41 | ignored_local_generated_or_sensitive |
| archive.zip | 25.67 | ignored_local_generated_or_sensitive |
| data/processed/supply_chain_orders.csv | 21.41 | ignored_local_generated_or_sensitive |
| powerbi/data/fact_orders.csv | 19.82 | ignored_local_generated_or_sensitive |
| powerbi/data/dim_customers.csv | 0.7400 | ignored_local_generated_or_sensitive |
| powerbi/data/dim_geography.csv | 0.3780 | ignored_local_generated_or_sensitive |
| src/supply_chain_pipeline.py | 0.1250 | repository_intended |
| powerbi/data/dim_date.csv | 0.0590 | ignored_local_generated_or_sensitive |

## Largest Repository-Intended Files
| path | size_mb | repository_status |
| --- | --- | --- |
| src/supply_chain_pipeline.py | 0.1250 | repository_intended |
| dashboard/supply_chain_delivery_dashboard.html | 0.0110 | repository_intended |
| reports/figures/monthly_sales_late_delivery_trend.svg | 0.0090 | repository_intended |
| outputs/source_sample_records.json | 0.0080 | repository_intended |
| powerbi/field_dictionary.csv | 0.0070 | repository_intended |
| validation/run_validation.py | 0.0070 | repository_intended |
| README.md | 0.0070 | repository_intended |
| outputs/repository_file_inventory.csv | 0.0060 | repository_intended |
| reports/figures/high_volume_regions_late_delivery.svg | 0.0050 | repository_intended |
| sql/business_analysis.sql | 0.0050 | repository_intended |
| validation/validation_results.csv | 0.0040 | repository_intended |
| reports/figures/top_categories_sales.svg | 0.0040 | repository_intended |

## Version-Controlled By Design
- `src/`, `run_pipeline.py`, and `requirements.txt`
- `sql/`
- `validation/`
- `docs/`, `reports/`, and `reports/figures/`
- `powerbi/` documentation, DAX, style guide, and theme files
- `dashboard/supply_chain_delivery_dashboard.html`
- small summary outputs in `outputs/` and `outputs/sql/`

## Ignored Local Or Generated Files
- `archive.zip`
- `data/raw/`
- `data/processed/`
- `powerbi/data/`
- `outputs/supply_chain.sqlite`
- `__pycache__/` and `*.pyc`

## Regeneration Commands
Place the source archive locally at `archive.zip`, then run:

```powershell
python run_pipeline.py
python validation/run_validation.py
```

The pipeline regenerates raw extracts, processed CSVs, SQLite outputs, Power BI-ready CSVs, dashboard files, validation outputs, and documentation from the local archive.
