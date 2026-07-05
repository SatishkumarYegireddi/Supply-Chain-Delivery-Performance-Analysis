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
    "PROJECT_STATUS.md",
    "docs/filter_propagation_validation.md",
    "docs/github_data_strategy.md",
    "docs/repository_readiness_report.md",
    "docs/dashboard_environment_inspection.md",
    "docs/resume_bullets.md",
    "docs/github_repository_description.md",
    "docs/linkedin_project_description.md",
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
