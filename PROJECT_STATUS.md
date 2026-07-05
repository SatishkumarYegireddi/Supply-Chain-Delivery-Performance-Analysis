# Project Status

## Status
Analysis and validation are complete. The remaining step is repository publication.

## Validated Scope
- Order-item rows: 180,519
- Distinct orders: 65,752
- Distinct customers: 20,652
- Date range: 2015-01 to 2018-01
- Python vs SQL KPI reconciliation: PASS
- Dashboard KPI and chart validation: PASS
- Automated project validation: PASS
- Repository-readiness validation: PASS

## Analytical Decisions
- Sales and profit are calculated at order-item grain.
- Delivery, delay, cancellation, and order counts are calculated at distinct-order grain.
- Access logs are excluded from the primary delivery model because no reliable order-level join exists.
- Sensitive customer fields are excluded from processed and Power BI-ready outputs.
- Raw and large generated datasets remain local and are excluded by `.gitignore`.

## Deliverables
- Reproducible Python pipeline
- SQLite analytical layer and SQL result exports
- EDA and business-insight reports
- Interactive four-tab HTML dashboard
- Power BI semantic-model specification, DAX library, theme, and implementation documentation
- Automated KPI, dashboard, privacy, and repository validation

A `.pbix` file is not included or claimed.
