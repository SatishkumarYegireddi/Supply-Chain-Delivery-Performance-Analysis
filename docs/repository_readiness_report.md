# Repository Readiness Report

## Status
Repository readiness checks are generated in `outputs/repository_readiness_checks.csv`.

| check | status | details |
| --- | --- | --- |
| repository_intended_files_under_100_mib | PASS |  |
| python_cache_artifacts_absent | PASS |  |
| dashboard_artifact_versionable | PASS | dashboard/supply_chain_delivery_dashboard.html size=11399 bytes |
| raw_archive_ignored | PASS | archive.zip size=26920609 bytes |
| large_processed_csv_ignored | PASS | data/processed/supply_chain_order_items.csv |
| powerbi_generated_data_ignored | PASS | powerbi/data/*.csv |

## Sensitive Data Audit
Raw data, the local source archive, full processed extracts, and Power BI CSV exports are ignored. Publishable outputs exclude raw customer email, password, street, first-name, and last-name values. The sample-record JSON is sanitized before writing.

## Dashboard Artifact
The finished dashboard is `dashboard/supply_chain_delivery_dashboard.html` and is intended to be committed because it is small and directly openable in a browser.
