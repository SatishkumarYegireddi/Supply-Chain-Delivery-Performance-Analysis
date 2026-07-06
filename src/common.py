from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pandas as pd


PROJECT_TITLE = "Supply Chain Delivery Performance Analysis"
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive.zip"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
OUTPUTS_DIR = ROOT / "outputs"
SQL_OUTPUTS_DIR = OUTPUTS_DIR / "sql"
SQL_DIR = ROOT / "sql"
POWERBI_DIR = ROOT / "powerbi"
POWERBI_DATA_DIR = POWERBI_DIR / "data"
VALIDATION_DIR = ROOT / "validation"
DASHBOARD_DIR = ROOT / "dashboard"

MAIN_SOURCE = "DataCoSupplyChainDataset.csv"
DESCRIPTION_SOURCE = "DescriptionDataCoSupplyChain.csv"
ACCESS_LOG_SOURCE = "tokenized_access_logs.csv"


def make_dirs() -> None:
    for folder in [
        RAW_DIR,
        PROCESSED_DIR,
        DOCS_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        OUTPUTS_DIR,
        SQL_OUTPUTS_DIR,
        SQL_DIR,
        POWERBI_DIR,
        POWERBI_DATA_DIR,
        VALIDATION_DIR,
        DASHBOARD_DIR,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")

def pct(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100 * float(value):.{digits}f}%"

def money(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"${float(value):,.{digits}f}"

def num(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{digits}f}"

def slug(name: str) -> str:
    value = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value

def md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    shown = df.head(max_rows).copy()
    if shown.empty:
        return "_No rows._"

    def fmt(value) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4f}" if abs(value) < 1 else f"{value:,.2f}"
        return str(value)

    headers = [str(col) for col in shown.columns]
    rows = [[fmt(value).replace("|", "\\|") for value in row] for row in shown.to_numpy()]
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, divider, *body])
