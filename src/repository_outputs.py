from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from .common import ARCHIVE, DASHBOARD_DIR, DOCS_DIR, OUTPUTS_DIR, POWERBI_DATA_DIR, POWERBI_DIR, PROCESSED_DIR, REPORTS_DIR, ROOT, VALIDATION_DIR, write_text

def repository_file_status(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    ignored_exact = {
        "archive.zip",
        "outputs/supply_chain.sqlite",
    }
    ignored_prefixes = (
        "data/raw/",
        "data/processed/",
        "powerbi/data/",
    )
    if (
        rel in ignored_exact
        or rel.startswith(ignored_prefixes)
        or "__pycache__" in parts
        or path.suffix == ".pyc"
        or rel.startswith(".git/")
    ):
        return "ignored_local_generated_or_sensitive"
    return "repository_intended"

def create_repository_checks() -> None:
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc_file in ROOT.rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)

    rows = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()
            rows.append(
                {
                    "path": rel,
                    "size_bytes": path.stat().st_size,
                    "size_mb": round(path.stat().st_size / 1_048_576, 3),
                    "repository_status": repository_file_status(path),
                }
            )

    inventory = pd.DataFrame(rows).sort_values("size_bytes", ascending=False)
    inventory.to_csv(OUTPUTS_DIR / "repository_file_inventory.csv", index=False)
    intended = inventory[inventory["repository_status"].eq("repository_intended")]
    too_large = intended[intended["size_bytes"] > 100 * 1024 * 1024]
    cache_artifacts = inventory[inventory["path"].str.contains("__pycache__", regex=False) | inventory["path"].str.endswith(".pyc")]
    dashboard_path = DASHBOARD_DIR / "supply_chain_delivery_dashboard.html"

    checks = pd.DataFrame(
        [
            {"check": "repository_intended_files_under_100_mib", "status": "PASS" if too_large.empty else "FAIL", "details": "; ".join(too_large["path"].tolist())},
            {"check": "python_cache_artifacts_absent", "status": "PASS" if cache_artifacts.empty else "FAIL", "details": "; ".join(cache_artifacts["path"].tolist())},
            {"check": "dashboard_artifact_versionable", "status": "PASS" if dashboard_path.exists() and repository_file_status(dashboard_path) == "repository_intended" else "FAIL", "details": f"{dashboard_path.relative_to(ROOT).as_posix()} size={dashboard_path.stat().st_size if dashboard_path.exists() else 0} bytes"},
            {"check": "raw_archive_ignored", "status": "PASS" if repository_file_status(ARCHIVE) != "repository_intended" else "FAIL", "details": f"archive.zip size={ARCHIVE.stat().st_size if ARCHIVE.exists() else 0} bytes"},
            {"check": "large_processed_csv_ignored", "status": "PASS" if repository_file_status(PROCESSED_DIR / "supply_chain_order_items.csv") != "repository_intended" else "FAIL", "details": "data/processed/supply_chain_order_items.csv"},
            {"check": "powerbi_generated_data_ignored", "status": "PASS" if repository_file_status(POWERBI_DATA_DIR / "fact_order_items.csv") != "repository_intended" else "FAIL", "details": "powerbi/data/*.csv"},
        ]
    )
    checks.to_csv(OUTPUTS_DIR / "repository_readiness_checks.csv", index=False)

def normalize_markdown_files() -> None:
    markdown_roots = [ROOT / "README.md", DOCS_DIR, REPORTS_DIR, POWERBI_DIR]
    files: list[Path] = []
    for item in markdown_roots:
        if item.is_file() and item.suffix == ".md":
            files.append(item)
        elif item.is_dir():
            files.extend(item.rglob("*.md"))

    for path in files:
        in_fence = False
        normalized = []
        for line in path.read_text(encoding="utf-8").splitlines():
            candidate = line[8:] if line.startswith("        ") else line
            if candidate.lstrip().startswith("```"):
                in_fence = not in_fence
            normalized.append(candidate)
        path.write_text("\n".join(normalized).rstrip() + "\n", encoding="utf-8")

def create_validation_script() -> None:
    write_text(
        VALIDATION_DIR / "run_validation.py",
        r'''
        import json
        from pathlib import Path
        import pandas as pd

        ROOT = Path(__file__).resolve().parents[1]

        required_files = [
            "archive.zip",
            "data/raw/DataCoSupplyChainDataset.csv",
            "data/raw/DescriptionDataCoSupplyChain.csv",
            "data/raw/tokenized_access_logs.csv",
            "data/processed/supply_chain_order_items.csv",
            "data/processed/supply_chain_orders.csv",
            "outputs/dataset_inventory.csv",
            "outputs/data_quality_issue_register.csv",
            "outputs/kpi_dictionary.csv",
            "outputs/kpi_validation.csv",
            "outputs/dashboard_validation.csv",
            "outputs/repository_file_inventory.csv",
            "outputs/repository_readiness_checks.csv",
            "outputs/sql/executive_kpi_summary.csv",
            "powerbi/data/fact_order_items.csv",
            "powerbi/data/fact_orders.csv",
            "powerbi/data/dim_shipping_mode.csv",
            "powerbi/data/dim_order_status.csv",
            "powerbi/model_specification.md",
            "powerbi/dax_measures.md",
            "powerbi/dashboard_blueprint.md",
            "powerbi/dashboard_build_guide.md",
            "powerbi/style_guide.md",
            "dashboard/supply_chain_delivery_dashboard.html",
            "README.md",
            "docs/dataset_relevance.md",
            "docs/data_cleaning_rules.md",
            "docs/kpi_dictionary.md",
            "docs/sql_analysis.md",
            "docs/validation_report.md",
            "docs/filter_propagation_validation.md",
        ]

        def repository_file_status(path: Path) -> str:
            rel = path.relative_to(ROOT).as_posix()
            parts = set(path.relative_to(ROOT).parts)
            ignored_exact = {"archive.zip", "outputs/supply_chain.sqlite"}
            ignored_prefixes = ("data/raw/", "data/processed/", "powerbi/data/")
            if (
                rel in ignored_exact
                or rel.startswith(ignored_prefixes)
                or "__pycache__" in parts
                or path.suffix == ".pyc"
                or rel.startswith(".git/")
                or rel.startswith(".agents/")
                    ):
                return "ignored_local_generated_or_sensitive"
            return "repository_intended"

        results = []
        for rel in required_files:
            path = ROOT / rel
            results.append({"check": f"required_file::{rel}", "status": "PASS" if path.exists() else "FAIL", "details": rel})

        items = pd.read_csv(ROOT / "data/processed/supply_chain_order_items.csv")
        orders = pd.read_csv(ROOT / "data/processed/supply_chain_orders.csv")
        validations = pd.read_csv(ROOT / "outputs/kpi_validation.csv")
        dashboard_validation = pd.read_csv(ROOT / "outputs/dashboard_validation.csv")
        repository_checks = pd.read_csv(ROOT / "outputs/repository_readiness_checks.csv")
        fact_orders = pd.read_csv(ROOT / "powerbi/data/fact_orders.csv")
        fact_items = pd.read_csv(ROOT / "powerbi/data/fact_order_items.csv")

        def add(check, condition, details=""):
            results.append({"check": check, "status": "PASS" if condition else "FAIL", "details": details})

        add("processed_dataset_not_empty", len(items) > 0, f"rows={len(items)}")
        add("orders_dataset_not_empty", len(orders) > 0, f"rows={len(orders)}")
        add("fact_orders_dataset_not_empty", len(fact_orders) > 0, f"rows={len(fact_orders)}")
        add("fact_order_items_dataset_not_empty", len(fact_items) > 0, f"rows={len(fact_items)}")
        add("order_item_id_exists", "order_item_id" in items.columns)
        add("order_id_exists", "order_id" in items.columns)
        add("order_item_id_unique", items["order_item_id"].nunique() == len(items), f"distinct={items['order_item_id'].nunique()}, rows={len(items)}")
        add("order_grain_unique", orders["order_id"].nunique() == len(orders), f"distinct={orders['order_id'].nunique()}, rows={len(orders)}")
        add("fact_orders_grain_unique", fact_orders["order_id"].nunique() == len(fact_orders), f"distinct={fact_orders['order_id'].nunique()}, rows={len(fact_orders)}")
        add("fact_items_order_count_matches_processed", fact_items["order_item_id"].nunique() == len(items), f"fact_items={len(fact_items)}, processed={len(items)}")
        add("late_rate_valid", orders["late_delivery_flag"].mean() >= 0 and orders["late_delivery_flag"].mean() <= 1)
        add("cancellation_rate_valid", orders["cancellation_flag"].mean() >= 0 and orders["cancellation_flag"].mean() <= 1)
        add("total_sales_positive", items["order_item_total"].sum() > 0)
        add("python_sql_kpis_pass", validations["validation_status"].eq("PASS").all())
        add("dashboard_validation_pass", dashboard_validation["status"].eq("PASS").all(), "; ".join(dashboard_validation.loc[dashboard_validation["status"] != "PASS", "check"].astype(str).tolist()))
        add("repository_readiness_pass", repository_checks["status"].eq("PASS").all(), "; ".join(repository_checks.loc[repository_checks["status"] != "PASS", "check"].astype(str).tolist()))

        expected = {
            "total_sales": 33054402.380216613,
            "total_profit": 3966902.974050357,
            "profit_margin": 0.1200113355074478,
            "total_orders": 65752,
            "total_order_items": 180519,
            "total_customers": 20652,
            "late_delivery_rate": 0.5482418785740357,
            "average_shipping_delay_days": 0.5666747779535223,
        }
        actual = {
            "total_sales": float(items["order_item_total"].sum()),
            "total_profit": float(items["benefit_per_order"].sum()),
            "profit_margin": float(items["benefit_per_order"].sum() / items["order_item_total"].sum()),
            "total_orders": int(orders["order_id"].nunique()),
            "total_order_items": int(len(items)),
            "total_customers": int(items["customer_id"].nunique()),
            "late_delivery_rate": float(orders["late_delivery_flag"].mean()),
            "average_shipping_delay_days": float(orders["shipping_delay_days"].mean()),
        }
        for key, expected_value in expected.items():
            tolerance = 0.0001 if "rate" in key or "margin" in key else 0.05
            add(f"baseline_kpi::{key}", abs(actual[key] - expected_value) <= tolerance, f"actual={actual[key]}, expected={expected_value}")

        sensitive_cols = {"customer_email", "customer_password", "customer_street", "customer_fname", "customer_lname"}
        add("processed_sensitive_columns_removed", sensitive_cols.isdisjoint(set(items.columns)), ", ".join(sorted(sensitive_cols.intersection(items.columns))))
        add("powerbi_customer_sensitive_columns_removed", sensitive_cols.isdisjoint(set(pd.read_csv(ROOT / "powerbi/data/dim_customers.csv", nrows=1).columns)), "dim_customers checked")
        public_sample_path = ROOT / "outputs/source_sample_records.json"

        public_sample_sensitive_tokens = {
            "email",
            "password",
            "street",
            "fname",
            "lname",
            "ip",
            "url",
            "image",
            "latitude",
            "longitude",
            "zipcode",
        }

        public_sample_data = json.loads(
            public_sample_path.read_text(encoding="utf-8")
        )

        public_sample_columns = {
            column.lower()
            for records in public_sample_data.values()
            for record in records
            for column in record.keys()
        }

        exposed_public_sample_columns = {
            column
            for column in public_sample_columns
            if any(
                token in column
                for token in public_sample_sensitive_tokens
            )
        }

        add(
            "public_sample_sensitive_columns_removed",
            len(exposed_public_sample_columns) == 0,
            ", ".join(sorted(exposed_public_sample_columns)),
        )
        cache_artifacts = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.pyc")]
        cache_artifacts.extend([p.relative_to(ROOT).as_posix() for p in ROOT.rglob("__pycache__") if p.is_dir()])
        add("cache_artifacts_absent", len(cache_artifacts) == 0, "; ".join(cache_artifacts))

        oversized = []
        for path in ROOT.rglob("*"):
            if path.is_file() and repository_file_status(path) == "repository_intended" and path.stat().st_size > 100 * 1024 * 1024:
                oversized.append(path.relative_to(ROOT).as_posix())
        add("repository_intended_files_under_100_mib", len(oversized) == 0, "; ".join(oversized))

        dashboard_path = ROOT / "dashboard/supply_chain_delivery_dashboard.html"
        dashboard_text = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
        for label in ["Executive Overview", "Delivery & Logistics", "Market & Commercial", "Diagnostic Detail"]:
            add(f"dashboard_tab::{label}", label in dashboard_text)

        out = pd.DataFrame(results)
        out.to_csv(ROOT / "validation" / "validation_results.csv", index=False)
        failed = out[out["status"] != "PASS"]
        if len(failed):
            print(out.to_string(index=False))
            raise SystemExit(1)
        print(out.to_string(index=False))
        ''',
    )

def final_audit() -> None:
    create_repository_checks()
    create_validation_script()
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc_file in ROOT.rglob("*.pyc"):
        pyc_file.unlink(missing_ok=True)
