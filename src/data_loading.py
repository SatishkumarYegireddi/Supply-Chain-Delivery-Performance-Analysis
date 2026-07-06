from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from .common import ARCHIVE, MAIN_SOURCE, OUTPUTS_DIR, RAW_DIR, slug

def extract_archive() -> list[str]:
    if not ARCHIVE.exists():
        raise FileNotFoundError("archive.zip is required at the project root.")
    extracted = []
    with zipfile.ZipFile(ARCHIVE) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = RAW_DIR / Path(member.filename).name
            if not target.exists():
                with zf.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            extracted.append(target.name)
    return extracted

def read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    return pd.read_csv(path, encoding="latin1", nrows=nrows, low_memory=False)

def profile_source_files() -> dict[str, pd.DataFrame]:
    inventory_rows = []
    missing_rows = []
    sample_records = {}
    raw_data = {}
    main_dataframe = None

    with zipfile.ZipFile(ARCHIVE) as zf:
        archive_members = {Path(info.filename).name: info for info in zf.infolist() if not info.is_dir()}

    for path in sorted(RAW_DIR.glob("*.csv")):
        df = read_csv(path)
        raw_data[path.name] = df
        if path.name == MAIN_SOURCE:
            main_dataframe = df
        duplicate_rows = int(df.duplicated().sum())
        missing = df.isna().sum()
        inferred = {col: str(dtype) for col, dtype in df.dtypes.items()}
        archive_info = archive_members.get(path.name)
        inventory_rows.append(
            {
                "filename": path.name,
                "file_type": path.suffix.lower().lstrip("."),
                "file_size_bytes": path.stat().st_size,
                "archive_uncompressed_bytes": archive_info.file_size if archive_info else None,
                "encoding_used": "latin1",
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": " | ".join(df.columns),
                "inferred_data_types": json.dumps(inferred, ensure_ascii=True),
                "duplicate_full_rows": duplicate_rows,
                "parsing_problems": "None detected by pandas read_csv with latin1",
            }
        )
        for col in df.columns:
            missing_rows.append(
                {
                    "filename": path.name,
                    "column_name": col,
                    "missing_count": int(missing[col]),
                    "missing_pct": float(missing[col] / len(df)) if len(df) else 0.0,
                    "inferred_dtype": str(df[col].dtype),
                    "unique_values": int(df[col].nunique(dropna=True)),
                }
            )
        sample = df.head(5).copy()

        sensitive_sample_tokens = {
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

        sensitive_sample_cols = [
            col
            for col in sample.columns
            if any(token in slug(col) for token in sensitive_sample_tokens)
        ]

        sample = sample.drop(columns=sensitive_sample_cols, errors="ignore")
        sample_records[path.name] = (
            sample.where(pd.notna(sample), None)
            .to_dict(orient="records")
        )

    inventory = pd.DataFrame(inventory_rows)
    missing_profile = pd.DataFrame(missing_rows)
    inventory.to_csv(OUTPUTS_DIR / "dataset_inventory.csv", index=False)
    missing_profile.to_csv(OUTPUTS_DIR / "missing_value_profile.csv", index=False)
    (OUTPUTS_DIR / "source_sample_records.json").write_text(
        json.dumps(sample_records, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )
    if main_dataframe is None:
        raise FileNotFoundError(
            f"Main analytical source not found: {MAIN_SOURCE}"
        )

    return raw_data
