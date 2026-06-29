from __future__ import annotations

import io
from datetime import date

import pandas as pd

_DATE_FORMATS = ("%d-%m-%Y","%Y/%m/%d","%m/%d/%Y")

REQUIRED_COLUMNS = {
    "txn_id","date","merchant","amount",
    "currency","status","category","account_id","notes"
}

def _parse_date(value: str) -> date | None:
    value = str(value).strip()
    
    for fmt in _DATE_FORMATS:
        try:
            from datetime import datetime
            return datetime.strptime(value,fmt).date()
        except ValueError:
            continue
    return None

def validate_columns(df: pd.DataFrame) -> list[str]:
    """Return list of missing required columns."""
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]

def clean_csv(content: bytes) -> tuple[pd.DataFrame, int, int]:
    """
    Clean raw CSV bytes
    
    Returns:
        df -> cleaned DateFrame
        raw_count -> rows before cleaning
        clean_count -> rows after cleaning
    """
    
    df = pd.read_csv(io.BytesIO(content), dtype=str)
    raw_count = len(df)
    
    # Normalise dates
    df["date"] = df["date"].apply(_parse_date)
    
    # Strip currency symbols & coerce to float
    df["amount"] = (
        df["amount"]
        .str.replace(r"[$,]","",regex=True)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )
    
    # Normalise enums
    df["status"] = df["status"].str.strip().str.upper()
    df["currency"] = df["currency"].str.strip().str.upper()
    
    # Fill blanks
    df["category"] = df["category"].str.strip().replace("", pd.NA)
    df["category"] = df["category"].fillna("Uncategorised")
    
    df["txn_id"] = df["txn_id"].str.strip().replace("", pd.NA)
    df["notes"] = df["notes"].str.strip().replace("", pd.NA)
    
    # Remove exact duplicate rows
    df = df.drop_duplicates()
    
    # Drop unrecoverable rows
    df = df.dropna(subset=["date","amount","merchant","account_id"])
    
    # Add pipeline-internal columns if absent
    for col in ("is_anomaly","anomaly_reason","llm_category","llm_raw_response","llm_failed"):
        if col not in df.columns:
            df[col] = pd.NA
            
    df = df.reset_index(drop=True)
    clean_count = len(df)
    return df, raw_count, clean_count