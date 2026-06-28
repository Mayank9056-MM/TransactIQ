from __future__ import annotations

import pandas as pd

# Brands that only operate in India
DOMESTIC_ONLY_BRANDS: set[str] = {
    "swiggy","zomato","ola","irctc","bigbasket","meesho","nykaa","blinkit","dunzo","zepto"
}

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mutates a copy of df, setting is_anomaly + anomaly_reason
    """
    
    # Statistical outliner per account
    medians = (
        df.groupby("account_id")["amount"]
        .median()
        .rename("_median")
    )
    
    df = df.join(medians, on="account_id")
    
    outlier_mask = df["amount"] > (3* df["_median"])
    df.loc[outlier_mask,"is_anomaly"] = True
    df.loc[outlier_mask,"anomaly_reason"] = df.loc[outlier_mask].apply(
        lambda r: f"amount {r['amount']:.2f} exceeds 3x account median {r['_median']:.2f}",
        axis=1
    )
    df = df.drop(columns=["_median"])
    
    # domestic-only merchant charged in USD
    usd_domestic_mask = (df["currency"] == "USD") & (
        df["merchant"].str.lower().str.strip().isin(DOMESTIC_ONLY_BRANDS)
    )
    
    df.loc[usd_domestic_mask, "is_anomaly"] = True
    df.loc[usd_domestic_mask,"anomaly_reason"] = df.loc[usd_domestic_mask].apply(
        lambda r: _append_reason(
            r["anomaly_reason"],
            f"Domestic merchant '{r['merchant']}' charged in USD"
        ),
        axis=1
    )
    
    #  notes explicitly flagged SUSPICIOUS
    suspicious_mask = (
        df["notes"].notna()
        & df["notes"].str.contains("suspicious",case=False,na=False)
    )
    df.loc[suspicious_mask,"is_anomaly"] = True
    df.loc[suspicious_mask,"anomaly_reason"] = df.loc[suspicious_mask].apply(
        lambda r: _append_reason(r["anomaly_reason"], "Note flagged as SUSPICIOUS"),
        axis=1
    )
    
    return df

def _append_reason(existing,new: str) -> str:
    if pd.isna(existing) or not existing:
        return new
    return f"{existing}; {new}"