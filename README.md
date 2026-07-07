<!-- # Supply Chain Delivery Performance Analysis

## Overview
An end-to-end supply chain analytics project focused on late-delivery risk, logistics performance, sales, and profitability. The workflow combines Python data preparation, grain-aware KPI design, SQLite SQL analysis, Python-to-SQL reconciliation, Power BI model specifications, automated validation, and a standalone multi-tab HTML dashboard.

![Dashboard overview](reports/figures/dashboard_overview.svg)

## Business Problem
Operations teams need to identify where late deliveries are concentrated and whether those operational risks overlap with material sales and profitability exposure. This analysis evaluates delivery performance at order grain while preserving order-item grain for commercial metrics.

## Dataset Source and Privacy
This project uses **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS**, Version 5, published by Fabian Constante, Fernando Silva, and António Pereira on Mendeley Data (2019), DOI `10.17632/8gx2fvg2k6.5`.

Dataset page: `https://data.mendeley.com/datasets/8gx2fvg2k6/5`

The source contains `DataCoSupplyChainDataset.csv`, `DescriptionDataCoSupplyChain.csv`, and `tokenized_access_logs.csv`. Raw files are not committed because the source includes customer-identifying fields. Processed and Power BI-ready outputs remove customer email, password, street, first name, and last name fields.

## Headline KPIs
| KPI | Result |
| --- | ---: |
| Total Sales | $33,054,402.4 |
| Total Profit | $3,966,903.0 |
| Profit Margin | 12.0% |
| Orders | 65,752 |
| Order Items | 180,519 |
| Customers | 20,652 |
| Late Delivery Rate | 54.8% |
| Average Shipping Delay | 0.6 days |
| Cancellation Rate | 2.1% |

## Analytical Workflow
1. Extract and inventory the three source files.
2. Profile data quality and document analytical scope.
3. Clean and enrich the order-item dataset.
4. Roll up distinct orders for delivery and cancellation KPIs.
5. Perform exploratory and segment analysis in Python.
6. Build a SQLite analytical layer and execute SQL KPI/business queries.
7. Reconcile Python and SQL KPI results.
8. Export a two-fact Power BI model specification and DAX library.
9. Generate the multi-tab HTML dashboard and static GitHub preview.
10. Run automated dashboard, privacy, and KPI checks.

## Data Model and Grain
- `fact_order_items`: 180,519 rows; one row per `order_item_id`. Used for sales, profit, product, and category analysis.
- `fact_orders`: 65,752 rows; one row per `order_id`. Used for late-delivery, shipping-delay, cancellation, and order-count KPIs.
- Product/category-filtered order KPIs follow the documented Power BI filter context for order-level delivery metrics.

## Key Business Insights
- 54.8% of distinct orders are late, making delivery reliability the primary operational risk in this dataset.
- Shipping-mode performance varies materially; service-level monitoring should combine late-delivery rate with order volume.
- High-volume regions deserve priority where order concentration and late-delivery exposure overlap.
- Category performance should be evaluated with profit margin alongside sales because revenue volume alone can hide weaker economics.

Detailed findings are in `reports/business_insights.md` and `reports/executive_summary.md`.

## HTML Dashboard
Open `dashboard/supply_chain_delivery_dashboard.html` directly in a browser. No local server is required. The dashboard contains four tabs:
- Executive Overview
- Delivery & Logistics Performance
- Market & Commercial Performance
- Diagnostic / Segment Detail

Headline KPI cards and major chart aggregates are reconciled in `outputs/dashboard_validation.csv`.

## SQL Analysis
The `sql/` directory contains schema, view, KPI, data-quality, and business-analysis queries. Executed query outputs are stored in `outputs/sql/`. Order-level delivery metrics are calculated from a distinct-order analytical view and reconciled against Python results in `outputs/kpi_validation.csv`.

## Power BI Model Artifacts
The `powerbi/` directory contains the model specification, DAX measures, report layout blueprint, build guide, style guide, field dictionary, and theme JSON. A `.pbix` file is **not** included or claimed. The completed browser-based deliverable is the standalone multi-tab HTML dashboard; the Power BI files document an implementation-ready semantic model and measure design.

## Tech Stack
- Python and pandas
- SQLite and SQL
- HTML, CSS, JavaScript, and SVG
- Power BI model design and DAX
- Automated validation with Python

## Project Structure
```text
dashboard/                Multi-tab HTML dashboard
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

## Unit Tests
Run the focused pytest suite from the project root:

```powershell
python -m pytest tests
```

## Validation
- Python vs SQL KPI reconciliation: PASS
- Dashboard KPI/chart validation: PASS
- Automated validation suite: PASS
See `validation/validation_results.csv`, `outputs/kpi_validation.csv`, and `outputs/dashboard_validation.csv`.

## Limitations
- This is a portfolio case study based on a public historical dataset, not a commissioned company engagement.
- The data does not include carrier, warehouse, inventory, or staffing features; recommendations are prioritization-oriented rather than causal.
- Clickstream access logs are excluded from the delivery model because no reliable order-level join is available.
- Postal-code analysis is de-emphasized because order ZIP code has high missingness.

## Conclusion
The analysis shows how order-grain logistics KPIs and item-grain commercial metrics can be combined without double counting. The resulting workflow identifies delivery-risk segments, quantifies commercial exposure, and validates the same headline KPIs across Python, SQL, and dashboard outputs. -->
# Supply Chain Delivery Performance Analysis

### End-to-End Supply Chain Analytics using Python, SQL, SQLite, and Power BI Semantic Modeling

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Analytics-orange?style=for-the-badge)
![Power BI](https://img.shields.io/badge/Power%20BI-DAX-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)

---

![Dashboard Overview](reports/figures/dashboard_overview.svg)

---

# Overview

This project presents an end-to-end supply chain analytics solution built using **Python, SQL, SQLite, and Power BI semantic modeling** to evaluate delivery performance, logistics efficiency, sales, profitability, and operational risk.

Unlike many portfolio projects that directly calculate KPIs from the raw dataset, this project introduces a **grain-aware analytical model** that separates **order-level operational metrics** from **order-item commercial metrics**, preventing duplicate counting while ensuring accurate reporting.

The project also validates every major KPI across **Python, SQL, and dashboard outputs**, making the analysis reproducible and analytically reliable.

---

# Business Problem

Supply chain teams need to answer critical business questions such as:

- Where are delivery delays concentrated?
- Which shipping methods perform poorly?
- Which regions require operational attention?
- Do logistics issues overlap with high-value commercial activity?

Because the source dataset is stored at the **order-item level**, directly calculating delivery KPIs would overcount orders containing multiple items.

This project solves that problem through a grain-aware analytical model that separates logistics KPIs from commercial metrics while preserving detailed sales analysis.

---

# Tech Stack

| Category | Technologies |
|-----------|--------------|
| Programming | Python, Pandas |
| Database | SQLite, SQL |
| Business Intelligence | Power BI Semantic Modeling, DAX |
| Visualization | HTML, CSS, JavaScript, SVG |
| Testing | Pytest |
| Version Control | Git, GitHub |

---

# Dataset

This project uses the **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS (Version 5)** dataset published by **Fabian Constante, Fernando Silva, and António Pereira** on **Mendeley Data (2019)**.

**DOI:** `10.17632/8gx2fvg2k6.5`

The dataset includes:

- `DataCoSupplyChainDataset.csv`
- `DescriptionDataCoSupplyChain.csv`
- `tokenized_access_logs.csv`

Raw files are intentionally excluded from the repository because they contain customer-identifying information. Processed datasets remove personally identifiable fields before analysis.

---

# Project Highlights

- End-to-end reproducible analytics pipeline
- Grain-aware analytical data model
- Python data cleaning & feature engineering
- SQLite analytical database
- SQL KPI and business analysis
- Python ↔ SQL KPI reconciliation
- Automated validation framework
- Power BI semantic model specification
- Interactive HTML dashboard
- Executive business reporting

---

# Headline KPIs

| KPI | Value |
|------|------:|
| Total Sales | **$33.05M** |
| Total Profit | **$3.97M** |
| Profit Margin | **12.0%** |
| Orders | **65,752** |
| Order Items | **180,519** |
| Customers | **20,652** |
| Late Delivery Rate | **54.8%** |
| Average Shipping Delay | **0.6 Days** |
| Cancellation Rate | **2.1%** |

---

# Solution Architecture

> Replace the placeholder below with your architecture diagram.

```markdown
![Solution Architecture](reports/figures/project_architecture.png)
```

---

# Analytical Workflow

1. Acquire and inventory the source datasets.
2. Clean and preprocess the raw data using Python.
3. Perform feature engineering and privacy-aware transformations.
4. Build separate analytical fact tables.
5. Perform exploratory data analysis.
6. Create the SQLite analytical layer.
7. Execute SQL KPI and business analysis queries.
8. Validate KPIs between Python and SQL.
9. Generate the interactive HTML dashboard and analytical reports.
10. Execute automated validation to ensure data quality and KPI consistency.

---

# Data Model

The project separates operational and commercial reporting into two analytical fact tables.

| Fact Table | Grain | Purpose |
|------------|-------|---------|
| `fact_orders` | One row per `order_id` | Delivery performance, shipping delays, cancellations, operational KPIs |
| `fact_order_items` | One row per `order_item_id` | Sales, profit, products, categories, and customer analysis |

### Why this Matters

The source dataset is stored at the **order-item grain**.

Calculating delivery KPIs directly from the raw dataset would duplicate multi-item orders and produce inaccurate operational metrics.

To ensure analytical correctness:

- Operational KPIs are calculated from **fact_orders**.
- Commercial KPIs are calculated from **fact_order_items**.
- Product and category filtering follows documented Power BI filter behavior.
- Every headline KPI is validated across Python, SQL, and dashboard outputs.

---

# Business Insights

The analysis identifies operational bottlenecks, commercial opportunities, and regional performance patterns that support data-driven supply chain decision-making.

### 🚚 Delivery Performance

- **54.8%** of distinct orders were delivered later than the scheduled date, highlighting delivery reliability as the primary operational challenge.
- Shipping performance varies across shipping modes, indicating opportunities to optimize logistics strategies and service-level agreements.
- High-order-volume regions experience greater operational exposure and should be prioritized for process improvement.

### 💰 Commercial Performance

- High revenue does not always correspond to high profitability.
- Several product categories generate strong sales but comparatively lower profit margins.
- Evaluating both sales and profit provides a more accurate measure of business performance than revenue alone.

### 📊 Market Insights

- Customer purchasing behavior differs across regions and product categories.
- Regional demand and delivery performance should be analyzed together to prioritize operational improvements.
- Combining operational KPIs with commercial metrics provides better decision support.

Detailed analysis is available in:

- `reports/business_insights.md`
- `reports/executive_summary.md`

---

# Interactive Dashboard

The project includes a standalone **interactive HTML dashboard** that can be opened directly in any modern web browser.

```text
dashboard/supply_chain_delivery_dashboard.html
```

### Dashboard Modules

- 📊 Executive Overview
- 🚚 Delivery & Logistics Performance
- 💰 Market & Commercial Performance
- 🔍 Diagnostic Detail

The dashboard provides:

- Executive KPI summary
- Delivery performance monitoring
- Shipping mode comparison
- Regional analysis
- Sales and profitability trends
- Customer and category insights

All dashboard KPIs are validated against Python and SQL outputs.

---

# SQL Analytics

SQLite is used as the analytical database layer for KPI generation and business analysis.

The SQL implementation includes:

- Database Schema
- Analytical Views
- KPI Queries
- Business Analysis Queries
- Validation Queries

SQL modules:

```text
schema.sql
views.sql
kpi_queries.sql
business_analysis.sql
validation_queries.sql
```

Generated SQL outputs are stored in:

```text
outputs/sql/
```

Order-level KPIs are calculated from a distinct-order analytical view to prevent duplicate counting.

---

# Power BI Semantic Model

Although a `.pbix` file is **not included**, the repository provides complete implementation-ready Power BI artifacts, including:

- Semantic Model Specification
- DAX Measure Library
- Dashboard Blueprint
- Build Guide
- Theme Configuration
- Field Dictionary
- Relationship Documentation
- Style Guide

These artifacts document the reporting model while keeping the repository lightweight and reproducible.

---

# Project Structure

```text
📦 Supply-Chain-Delivery-Performance-Analysis
│
├── dashboard/          Interactive HTML dashboard
├── data/
│   ├── raw/            Source data (Git ignored)
│   └── processed/      Processed analytical datasets
├── docs/               Technical documentation
├── outputs/            KPI & validation outputs
├── powerbi/            Semantic model & DAX artifacts
├── reports/            Business reports & figures
├── sql/                SQL scripts
├── src/                Python analytics pipeline
├── tests/              Unit tests
├── validation/         Validation framework
│
├── run_pipeline.py
├── requirements.txt
└── README.md
```

---

# Reproducing the Project

### 1. Download the Dataset

Download **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS (Version 5)** from Mendeley Data.

Create a ZIP archive named:

```text
archive.zip
```

containing:

- `DataCoSupplyChainDataset.csv`
- `DescriptionDataCoSupplyChain.csv`
- `tokenized_access_logs.csv`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Pipeline

```bash
python run_pipeline.py
```

### 4. Execute Validation

```bash
python validation/run_validation.py
```

The pipeline automatically generates:

- Processed datasets
- SQLite database
- SQL outputs
- Dashboard
- Reports
- Figures
- Validation results
- Power BI-ready datasets

---

# Unit Testing

Run the automated test suite:

```bash
python -m pytest tests
```

---

# Validation

| Validation Check | Status |
|------------------|:------:|
| Python vs SQL KPI Reconciliation | ✅ PASS |
| Dashboard KPI Validation | ✅ PASS |
| Dashboard Aggregate Validation | ✅ PASS |
| Automated Validation Suite | ✅ PASS |
| Privacy Compliance Checks | ✅ PASS |

Validation reports:

```text
validation/validation_results.csv
outputs/kpi_validation.csv
outputs/dashboard_validation.csv
```

---

# Limitations

- This is a portfolio project based on a public historical dataset.
- The dataset does not include warehouse, inventory, carrier, or workforce planning information.
- Clickstream logs are excluded because no reliable order-level relationship exists.
- Postal-code analysis is limited due to high missingness.
- Recommendations are prioritization-oriented rather than causal.

---

# Future Improvements

- PostgreSQL implementation
- Interactive Power BI (`.pbix`) dashboard
- Cloud deployment
- Real-time data pipeline
- Delivery delay forecasting
- CI/CD automation

---

# Conclusion

This project demonstrates an end-to-end supply chain analytics workflow that transforms raw operational data into reliable, decision-ready business insights.

A key contribution is the implementation of a **grain-aware analytical model** that separates operational KPIs from commercial metrics, preventing duplicate counting while preserving detailed sales analysis.

By combining Python, SQL, semantic data modeling, automated validation, and an interactive dashboard, the project emphasizes analytical correctness, reproducibility, and business value—skills directly applicable to modern **Data Analyst** and **Business Intelligence** roles.

---

# Acknowledgements

**Dataset:** DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS (Version 5)

**Authors:** Fabian Constante, Fernando Silva, and António Pereira

**Publisher:** Mendeley Data

**DOI:** `10.17632/8gx2fvg2k6.5`

---

# Contributors

| Contributor | Contributions |
|-------------|---------------|
| **Yegireddi Satish Kumar** | Project architecture, Python analytics pipeline, SQL development, data modeling, validation framework, dashboard implementation, technical documentation, and repository management. |
| **Gunuputi Doondy Satwika** | Business analysis, documentation, repository review, testing, quality assurance, project presentation, and repository refinement. |

This project was completed through collaborative planning, implementation, validation, documentation, testing, and continuous repository improvement.