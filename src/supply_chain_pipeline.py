from __future__ import annotations

import pandas as pd

from .analysis_outputs import build_eda_outputs, create_sql_layer
from .common import MAIN_SOURCE, OUTPUTS_DIR, PROCESSED_DIR, make_dirs
from .data_loading import extract_archive, profile_source_files
from .data_preparation import derive_clean_dataset, order_level
from .metrics import build_data_quality, build_kpi_dictionary, calculate_metrics, validate_kpis
from .powerbi_outputs import build_powerbi_model
from .reporting import create_docs
from .repository_outputs import final_audit, normalize_markdown_files
from .visualization import save_figures


def main() -> None:
    make_dirs()
    extracted = extract_archive()
    raw_data = profile_source_files()
    if MAIN_SOURCE not in raw_data:
        raise FileNotFoundError(f"{MAIN_SOURCE} not found after extraction.")

    df = derive_clean_dataset(raw_data[MAIN_SOURCE])
    orders = order_level(df)
    df.to_csv(PROCESSED_DIR / "supply_chain_order_items.csv", index=False)
    orders.to_csv(PROCESSED_DIR / "supply_chain_orders.csv", index=False)

    metrics = calculate_metrics(df, orders)
    pd.DataFrame([metrics.__dict__]).to_csv(OUTPUTS_DIR / "python_kpi_summary.csv", index=False)
    dq = build_data_quality(df, orders)
    kpis = build_kpi_dictionary()
    eda = build_eda_outputs(df, orders)
    save_figures(df, orders)
    sql_metrics = create_sql_layer(df)
    validation = validate_kpis(metrics, sql_metrics)
    build_powerbi_model(df, orders)
    create_docs(raw_data, df, orders, metrics, dq, kpis, eda, validation)
    normalize_markdown_files()
    final_audit()
    print(f"Pipeline complete. Extracted files: {', '.join(extracted)}")
    print(f"Processed order-item rows: {len(df):,}")
    print(f"Distinct orders: {len(orders):,}")
    print(f"KPI validation: {'PASS' if validation['validation_status'].eq('PASS').all() else 'FAIL'}")
