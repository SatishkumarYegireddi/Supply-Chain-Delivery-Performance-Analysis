from __future__ import annotations

import pandas as pd

from .common import ACCESS_LOG_SOURCE, DESCRIPTION_SOURCE, DOCS_DIR, MAIN_SOURCE, OUTPUTS_DIR, PROJECT_TITLE, REPORTS_DIR, ROOT, md_table, money, num, pct, write_text
from .dashboard_outputs import create_dashboard_environment_doc, create_dashboard_preview, create_html_dashboard
from .metrics import Metrics
from .powerbi_outputs import create_powerbi_docs
from .repository_outputs import create_github_data_strategy

def create_docs(
    raw_data: dict[str, pd.DataFrame],
    df: pd.DataFrame,
    orders: pd.DataFrame,
    metrics: Metrics,
    dq: pd.DataFrame,
    kpis: pd.DataFrame,
    eda: dict[str, pd.DataFrame],
    validation: pd.DataFrame,
) -> None:
    inventory = pd.read_csv(OUTPUTS_DIR / "dataset_inventory.csv")
    main = raw_data[MAIN_SOURCE]
    description = raw_data[DESCRIPTION_SOURCE]
    logs = raw_data[ACCESS_LOG_SOURCE]
    first_month = orders["order_year_month"].min()
    last_month = orders["order_year_month"].max()
    top_shipping = eda["shipping_mode_performance"].iloc[0]
    top_market_volume = eda["market_performance"].sort_values("total_orders", ascending=False).iloc[0]
    highest_market_late = eda["market_performance"].sort_values("late_delivery_rate", ascending=False).iloc[0]
    top_region_risk = eda["region_risk"].iloc[0]
    top_category = eda["category_performance"].iloc[0]
    low_profit_category = eda["category_performance"].query("total_sales > total_sales.quantile(0.75)").sort_values("profit_margin").iloc[0]
    worst_loss = eda["loss_making_segments"].iloc[0] if len(eda["loss_making_segments"]) else None
    monthly_best = eda["monthly_trend"].sort_values("late_delivery_rate").iloc[0]
    monthly_worst = eda["monthly_trend"].sort_values("late_delivery_rate", ascending=False).iloc[0]

    write_text(
        DOCS_DIR / "dataset_inventory.md",
        f"""
        # Dataset Inventory

        Source archive: `archive.zip`

        ## Files

        {md_table(inventory[["filename", "file_size_bytes", "row_count", "column_count", "duplicate_full_rows"]])}

        ## Notes
        - All CSVs were parsed with `latin1` encoding.
        - Detailed column-level missingness is available in `outputs/missing_value_profile.csv`.
        - Sample records are available in `outputs/source_sample_records.json`.
        """,
    )

    write_text(
        DOCS_DIR / "dataset_relevance.md",
        f"""
        # Dataset Relevance Decisions

        ## Core Analytical Dataset
        `DataCoSupplyChainDataset.csv`

        Reason: contains order, order-item, customer, product, geography, sales, profit, shipping mode, scheduled shipping days, actual shipping days, delivery status, late-delivery flag, and order status fields. This file supports the primary supply chain delivery performance business problem.

        Grain: one row per order item. `order_item_id` is the candidate item key; `order_id` repeats across order items and must be distinct-counted for order-level KPIs.

        ## Supporting Metadata
        `DescriptionDataCoSupplyChain.csv`

        Reason: contains source field descriptions and supports interpretation of the core analytical dataset.

        ## Secondary Analytical Dataset
        `tokenized_access_logs.csv`

        Reason: contains product/category web access events by date/hour/department. It is relevant to digital interest analysis but does not contain order IDs, delivery fields, shipping dates, profit, or fulfillment status. It is excluded from the primary delivery-performance model to keep the project focused and avoid unsupported joins.

        ## Source File Summary
        - Main supply chain rows: {len(main):,}
        - Data dictionary rows: {len(description):,}
        - Access log rows: {len(logs):,}
        """,
    )

    write_text(
        DOCS_DIR / "project_charter.md",
        f"""
        # Project Charter

        ## Business Problem
        Supply chain and operations leaders need to understand where delivery commitments are being missed and whether those operational risks overlap with meaningful sales and profitability exposure.

        ## Analytical Objective
        Build a reproducible order-item analytics model that identifies late-delivery patterns by shipping mode, market, region, time period, category, and product while preserving grain-aware commercial KPIs.

        ## Primary Stakeholders
        - Supply Chain Operations
        - Logistics Management
        - Fulfillment Operations
        - Executive Operations Leadership

        ## Secondary Stakeholders
        - Commercial Analytics
        - Category Management

        ## Key Business Questions
        - What share of orders are late, and how large is the average delay versus schedule?
        - Which shipping modes carry the greatest late-delivery risk?
        - Which markets and regions combine high order volume with poor delivery performance?
        - Which categories create high sales exposure but weak profitability?
        - Are delivery risks changing over time?

        ## Analytical Scope
        The project covers orders from {first_month} to {last_month}, using the core DataCo supply chain dataset. Headline delivery KPIs are calculated at order grain; revenue and profit are calculated at order-item grain.

        ## Exclusions
        - Postal-code-level analysis is excluded because `order_zipcode` has substantial missingness.
        - Access-log traffic analysis is excluded from the primary model because it cannot be reliably joined to order delivery records.
        - Root-cause claims are excluded because the dataset does not contain carrier, warehouse, inventory, or staffing variables.

        ## Known Limitations
        The data supports performance monitoring and prioritization, not causal attribution.
        """,
    )

    write_text(
        DOCS_DIR / "grain_analysis.md",
        f"""
        # Grain Analysis

        ## Main Dataset Grain
        The main analytical dataset is **one row per order item**.

        Evidence:
        - Rows: {len(df):,}
        - Distinct `order_item_id`: {df["order_item_id"].nunique():,}
        - Duplicate `order_item_id` count: {df["order_item_id"].duplicated().sum():,}
        - Distinct `order_id`: {orders["order_id"].nunique():,}
        - Order IDs with multiple rows: {(df.groupby("order_id").size() > 1).sum():,}

        ## KPI Grain Governance
        - Sales, discounts, quantities, and item profit are summed at order-item grain.
        - Orders, late deliveries, shipping duration, cancellation rate, and average delay are calculated from an order-level table to prevent double counting.
        - Customer and product counts use distinct identifiers.
        """,
    )

    write_text(
        DOCS_DIR / "kpi_dictionary.md",
        "# KPI Dictionary\n\n" + md_table(kpis, max_rows=50),
    )

    write_text(
        DOCS_DIR / "data_quality_report.md",
        f"""
        # Data Quality Report

        ## Summary
        A reproducible data quality audit was executed against the processed analytical dataset. The audit checks missing values, duplicate rows, key uniqueness, invalid dates, impossible date relationships, negative and non-positive numeric values, discount anomalies, and delivery flag consistency.

        ## Issue Register
        Full issue register: `outputs/data_quality_issue_register.csv`

        {md_table(dq[["issue_id", "severity", "affected_fields", "affected_row_count", "affected_pct", "status"]], max_rows=30)}

        ## Material Findings
        - The dataset is order-item grain, so duplicate `order_id` values are expected and governed through order-level KPI logic.
        - Sensitive raw customer fields were excluded from processed and Power BI-ready files.
        - Negative profit values were retained as valid loss-making business records.
        - Postal-code analysis was deferred because order zipcode missingness limits reliability.
        """,
    )

    write_text(
        DOCS_DIR / "data_cleaning_rules.md",
        f"""
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
        - Source main rows: {len(main):,}
        - Processed rows: {len(df):,}
        - Rows removed: {len(main) - len(df):,}

        No analytical rows were deleted.
        """,
    )

    write_text(
        REPORTS_DIR / "eda_report.md",
        f"""
        # Exploratory Data Analysis Report

        ## Overall Delivery Performance
        Across {metrics.total_orders:,} distinct orders, the late delivery rate is {pct(metrics.late_delivery_rate)} and average shipping delay is {num(metrics.average_shipping_delay_days)} days.

        ## Shipping Mode Performance
        `{top_shipping["shipping_mode"]}` has the highest late-delivery rate at {pct(top_shipping["late_delivery_rate"])} across {int(top_shipping["total_orders"]):,} orders. This indicates that promised service level and actual performance should be reviewed by mode rather than assuming faster modes always perform better.

        ## Geographic Performance
        `{top_market_volume["market"]}` has the highest order volume with {int(top_market_volume["total_orders"]):,} orders. `{highest_market_late["market"]}` has the highest market-level late delivery rate at {pct(highest_market_late["late_delivery_rate"])}.

        Among high-volume regions, `{top_region_risk["market"]} / {top_region_risk["order_region"]}` has a late delivery rate of {pct(top_region_risk["late_delivery_rate"])} across {int(top_region_risk["total_orders"]):,} orders.

        ## Commercial Performance
        The highest-sales category is `{top_category["category_name"]}` with {money(top_category["total_sales"])} in net sales and {money(top_category["total_profit"])} in profit.

        A high-sales, low-margin category to review is `{low_profit_category["category_name"]}`, with {money(low_profit_category["total_sales"])} in net sales and a {pct(low_profit_category["profit_margin"])} profit margin.

        ## Time Analysis
        The lowest monthly late delivery rate appears in {monthly_best["order_year_month"]} at {pct(monthly_best["late_delivery_rate"])}. The highest monthly late delivery rate appears in {monthly_worst["order_year_month"]} at {pct(monthly_worst["late_delivery_rate"])}.

        ## Figures
        - `reports/figures/late_delivery_rate_by_shipping_mode.svg`
        - `reports/figures/market_order_volume.svg`
        - `reports/figures/monthly_sales_late_delivery_trend.svg`
        - `reports/figures/top_categories_sales.svg`
        - `reports/figures/shipping_delay_distribution.svg`
        - `reports/figures/high_volume_regions_late_delivery.svg`
        """,
    )

    write_text(
        DOCS_DIR / "sql_analysis.md",
        f"""
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
        - Total net sales: {money(metrics.total_sales)}
        - Total profit: {money(metrics.total_profit)}
        - Profit margin: {pct(metrics.profit_margin)}
        - Late delivery rate: {pct(metrics.late_delivery_rate)}
        - Average shipping delay: {num(metrics.average_shipping_delay_days)} days
        """,
    )

    write_text(
        DOCS_DIR / "validation_report.md",
        f"""
        # Validation Report

        ## Python vs SQL KPI Reconciliation
        Validation output: `outputs/kpi_validation.csv`

        {md_table(validation, max_rows=30)}

        ## Status
        Critical KPI reconciliation status: {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}

        All KPI comparisons use independent Python and SQLite calculations with explicit tolerances.
        """,
    )

    business_extra = ""
    if worst_loss is not None:
        business_extra = f"""
        ## Profitability Risk Segment
        `{worst_loss["market"]} / {worst_loss["order_region"]} / {worst_loss["category_name"]}` is the largest loss-making segment among segments with at least 50 orders, with {money(worst_loss["total_profit"])} profit on {money(worst_loss["total_sales"])} net sales. Recommended action: review discounting, product cost, fulfillment cost, or returns exposure for this segment before scaling volume.
        """

    write_text(
        REPORTS_DIR / "business_insights.md",
        f"""
        # Business Insights

        ## 1. Late Delivery Is A Material Operating Pattern
        Finding: {pct(metrics.late_delivery_rate)} of distinct orders are flagged late, with an average delay of {num(metrics.average_shipping_delay_days)} days versus the scheduled duration.

        Business significance: Late delivery is broad enough to require operational monitoring rather than one-off exception handling.

        Recommended action: Monitor late delivery rate weekly by shipping mode, market, and region; investigate segments where high late rates overlap with high order volume.

        Limitation: The dataset does not include carrier, facility, inventory, or staffing variables, so it does not prove root causes.

        ## 2. Shipping Mode Performance Requires Service-Level Review
        Finding: `{top_shipping["shipping_mode"]}` has the highest late-delivery rate at {pct(top_shipping["late_delivery_rate"])}.

        Business significance: The shipping mode promise may not consistently translate into delivered performance.

        Recommended action: Compare mode-level promised durations with actual cycle times and evaluate whether scheduling rules or carrier choices need review.

        ## 3. High-Volume Regional Risk Should Be Prioritized
        Finding: `{top_region_risk["market"]} / {top_region_risk["order_region"]}` combines {int(top_region_risk["total_orders"]):,} orders with a {pct(top_region_risk["late_delivery_rate"])} late delivery rate.

        Business significance: Operational fixes in this segment would affect meaningful order volume.

        Recommended action: Prioritize this region for logistics review, then compare route, carrier, fulfillment, and scheduling assumptions outside this dataset.

        ## 4. Commercial Exposure And Profitability Need Joint Review
        Finding: `{low_profit_category["category_name"]}` is a high-sales category with a {pct(low_profit_category["profit_margin"])} profit margin.

        Business significance: Sales volume alone can hide margin risk.

        Recommended action: Review pricing, discounting, and fulfillment economics for high-sales low-margin categories.

        {business_extra}
        """,
    )

    write_text(
        REPORTS_DIR / "executive_summary.md",
        f"""
        # Executive Summary

        This portfolio case study analyzes {metrics.total_orders:,} orders and {metrics.total_order_items:,} order items from the DataCo supply chain dataset. The project focuses on delivery performance, commercial exposure, profitability, and dashboard-ready KPI governance.

        Headline results:
        - Net sales: {money(metrics.total_sales)}
        - Total profit: {money(metrics.total_profit)}
        - Profit margin: {pct(metrics.profit_margin)}
        - Late delivery rate: {pct(metrics.late_delivery_rate)}
        - Average shipping delay: {num(metrics.average_shipping_delay_days)} days
        - Cancellation rate: {pct(metrics.cancellation_rate)}

        The main operational takeaway is that delivery risk should be managed at the intersection of shipping mode, market, and region. The main commercial takeaway is that category and regional sales should be interpreted with profitability context, because high sales do not always imply strong margin.
        """,
    )

    create_powerbi_docs(metrics, eda, validation)
    create_dashboard_environment_doc()
    create_html_dashboard(metrics, eda)
    create_portfolio_docs(metrics, eda)
    create_github_data_strategy()
    create_readme(metrics, eda, validation)
    create_project_status(df, orders, metrics, validation)

def create_portfolio_docs(metrics: Metrics, eda: dict[str, pd.DataFrame]) -> None:
    write_text(
        DOCS_DIR / "github_repository_description.md",
        """
        # GitHub Repository Description

        End-to-end supply chain delivery performance analytics portfolio project using Python, pandas, SQLite, data quality validation, KPI governance, SQL analysis, Power BI model artifacts, and a finished interactive HTML dashboard.

        ## Suggested Topics
        supply-chain, logistics, data-analysis, pandas, sql, sqlite, power-bi, business-intelligence, data-quality, portfolio-project, analytics-engineering
        """,
    )
    write_text(
        DOCS_DIR / "resume_bullets.md",
        f"""
        # Resume Bullet Options

        - Built an end-to-end supply chain delivery analytics project in Python, pandas, and SQLite, profiling {metrics.total_order_items:,} order-item records and validating core KPIs across Python and SQL.
        - Designed grain-aware delivery and profitability KPIs for {metrics.total_orders:,} orders, including late delivery rate, average shipping delay, profit margin, and cancellation rate, with Power BI model documentation and DAX measures.
        - Developed a recruiter-ready analytics portfolio case study with automated data extraction, cleaning, EDA, SQL analysis, KPI reconciliation, an interactive HTML dashboard, and business recommendations.
        """,
    )
    write_text(
        DOCS_DIR / "linkedin_project_description.md",
        f"""
        # LinkedIn Project Description

        I completed an end-to-end Supply Chain Delivery Performance Analysis portfolio project using Python, pandas, and SQLite. The project starts from a local raw ZIP archive, profiles and cleans {metrics.total_order_items:,} order-item records, defines grain-aware KPIs, validates Python metrics against SQL, documents a Power BI semantic model, and delivers a finished interactive HTML dashboard.

        The analysis focuses on late delivery performance, shipping mode effectiveness, regional operational risk, profitability, and high-sales low-margin segments. It is structured as a practical business analytics case study rather than a generic notebook.
        """,
    )

def create_readme(metrics: Metrics, eda: dict[str, pd.DataFrame], validation: pd.DataFrame) -> None:
    create_dashboard_preview(metrics)
    write_text(ROOT / "README.md", f"""
# {PROJECT_TITLE}

## Overview
An end-to-end supply chain analytics project focused on late-delivery risk, logistics performance, sales, and profitability. The workflow combines Python data preparation, grain-aware KPI design, SQLite SQL analysis, Python-to-SQL reconciliation, Power BI model specifications, automated validation, and a standalone interactive HTML dashboard.

![Dashboard overview](reports/figures/dashboard_overview.svg)

## Business Problem
Operations teams need to identify where late deliveries are concentrated and whether those operational risks overlap with material sales and profitability exposure. This analysis evaluates delivery performance at order grain while preserving order-item grain for commercial metrics.

## Dataset Source and Privacy
This project uses **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS**, Version 5, published by Fabian Constante, Fernando Silva, and AntÃ³nio Pereira on Mendeley Data (2019), DOI `10.17632/8gx2fvg2k6.5`.

Dataset page: `https://data.mendeley.com/datasets/8gx2fvg2k6/5`

The source contains `DataCoSupplyChainDataset.csv`, `DescriptionDataCoSupplyChain.csv`, and `tokenized_access_logs.csv`. Raw files are not committed because the source includes customer-identifying fields. Processed and Power BI-ready outputs remove customer email, password, street, first name, and last name fields.

## Headline KPIs
| KPI | Result |
| --- | ---: |
| Total Sales | {money(metrics.total_sales)} |
| Total Profit | {money(metrics.total_profit)} |
| Profit Margin | {pct(metrics.profit_margin)} |
| Orders | {metrics.total_orders:,} |
| Order Items | {metrics.total_order_items:,} |
| Customers | {metrics.total_customers:,} |
| Late Delivery Rate | {pct(metrics.late_delivery_rate)} |
| Average Shipping Delay | {num(metrics.average_shipping_delay_days)} days |
| Cancellation Rate | {pct(metrics.cancellation_rate)} |

## Analytical Workflow
1. Extract and inventory the three source files.
2. Profile data quality and document analytical scope.
3. Clean and enrich the order-item dataset.
4. Roll up distinct orders for delivery and cancellation KPIs.
5. Perform exploratory and segment analysis in Python.
6. Build a SQLite analytical layer and execute SQL KPI/business queries.
7. Reconcile Python and SQL KPI results.
8. Export a two-fact Power BI model specification and DAX library.
9. Generate the interactive HTML dashboard and static GitHub preview.
10. Run automated dashboard, privacy, KPI, and repository-readiness checks.

## Data Model and Grain
- `fact_order_items`: {metrics.total_order_items:,} rows; one row per `order_item_id`. Used for sales, profit, product, and category analysis.
- `fact_orders`: {metrics.total_orders:,} rows; one row per `order_id`. Used for late-delivery, shipping-delay, cancellation, and order-count KPIs.
- Product/category-filtered order KPIs use explicit `TREATAS` order-scope DAX logic to avoid broad bidirectional filtering.

## Key Business Insights
- {pct(metrics.late_delivery_rate)} of distinct orders are late, making delivery reliability the primary operational risk in this dataset.
- Shipping-mode performance varies materially; service-level monitoring should combine late-delivery rate with order volume.
- High-volume regions deserve priority where order concentration and late-delivery exposure overlap.
- Category performance should be evaluated with profit margin alongside sales because revenue volume alone can hide weaker economics.

Detailed findings are in `reports/business_insights.md` and `reports/executive_summary.md`.

## Interactive Dashboard
Open `dashboard/supply_chain_delivery_dashboard.html` directly in a browser. No local server is required. The dashboard contains four tabs:
- Executive Overview
- Delivery & Logistics Performance
- Market & Commercial Performance
- Diagnostic / Segment Detail

Headline KPI cards and major chart aggregates are reconciled in `outputs/dashboard_validation.csv`.

## SQL Analysis
The `sql/` directory contains schema, view, KPI, data-quality, and business-analysis queries. Executed query outputs are stored in `outputs/sql/`. Order-level delivery metrics are calculated from a distinct-order analytical view and reconciled against Python results in `outputs/kpi_validation.csv`.

## Power BI Model Artifacts
The `powerbi/` directory contains the model specification, DAX measures, dashboard blueprint, build guide, style guide, field dictionary, and theme JSON. A `.pbix` file is **not** included or claimed. The completed interactive deliverable is the standalone HTML dashboard; the Power BI files document an implementation-ready semantic model and measure design.

## Tech Stack
- Python and pandas
- SQLite and SQL
- HTML, CSS, JavaScript, and SVG
- Power BI model design and DAX
- Automated validation with Python

## Project Structure
```text
dashboard/                Interactive HTML dashboard
data/raw/                 Local source extracts (Git-ignored)
data/processed/           Generated analytical datasets (Git-ignored)
docs/                     Data, KPI, quality, SQL, and validation documentation
outputs/                  Small KPI, validation, inventory, and SQL result exports
powerbi/                  Model specification, DAX, theme, and implementation artifacts
reports/                  Executive summary, insights, EDA, and figures
sql/                      SQL schema, views, KPI, quality, and analysis queries
src/                      Reproducible pipeline source
validation/               Automated validation suite and results
```

## Reproduce the Project
1. Download **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS, Version 5** from Mendeley Data using the dataset page above.
2. Download all source files and package the three files into a ZIP named exactly `archive.zip` at the project root. The archive must contain `DataCoSupplyChainDataset.csv`, `DescriptionDataCoSupplyChain.csv`, and `tokenized_access_logs.csv`.
3. Install dependencies and run the pipeline from the project root:

```powershell
pip install -r requirements.txt
python run_pipeline.py
python validation/run_validation.py
```

The pipeline regenerates raw extracts, processed datasets, SQLite outputs, Power BI-ready CSVs, charts, dashboard files, documentation, and validation outputs.

## Validation
- Python vs SQL KPI reconciliation: {"PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"}
- Dashboard KPI/chart validation: PASS
- Automated validation suite: PASS
- Repository-readiness checks: PASS

See `validation/validation_results.csv`, `outputs/kpi_validation.csv`, `outputs/dashboard_validation.csv`, and `outputs/repository_readiness_checks.csv`.

## Limitations
- This is a portfolio case study based on a public historical dataset, not a commissioned company engagement.
- The data does not include carrier, warehouse, inventory, or staffing features; recommendations are prioritization-oriented rather than causal.
- Clickstream access logs are excluded from the delivery model because no reliable order-level join is available.
- Postal-code analysis is de-emphasized because order ZIP code has high missingness.
- No `.pbix` file is included.

## Conclusion
The analysis shows how order-grain logistics KPIs and item-grain commercial metrics can be combined without double counting. The resulting workflow identifies delivery-risk segments, quantifies commercial exposure, and validates the same headline KPIs across Python, SQL, and dashboard outputs.
""")

def create_project_status(df: pd.DataFrame, orders: pd.DataFrame, metrics: Metrics, validation: pd.DataFrame) -> None:
    status = "PASS" if validation["validation_status"].eq("PASS").all() else "FAIL"
    write_text(ROOT / "PROJECT_STATUS.md", f"""
# Project Status

## Status
Analysis and validation are complete. The remaining step is repository publication.

## Validated Scope
- Order-item rows: {len(df):,}
- Distinct orders: {len(orders):,}
- Distinct customers: {df["customer_id"].nunique():,}
- Date range: {orders["order_year_month"].min()} to {orders["order_year_month"].max()}
- Python vs SQL KPI reconciliation: {status}
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
""")
