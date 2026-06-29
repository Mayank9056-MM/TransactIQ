from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from app.db.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_summary import JobSummary
from app.models.transaction import Transaction
from app.services import anomaly_detector, csv_processor, llm_service
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="transactiq.process_job",
    max_retries=0,
    acks_late=True,
)
def process_job(self, job_id: int) -> None:
    db = SessionLocal()
    try:
        # load job
        job: Job | None = db.get(Job, job_id)
        if not job:
            logger.error("Job %d not found",job_id)
            return
        
        job.status = JobStatus.PROCESSING
        db.commit()
        logger.info("Job %d: processing started", job_id)
        
        # Read & clean CSV
        with open(job.file_path,"rb") as fh:
            content = fh.read()
            
        df, raw_count, clean_count = csv_processor.clean_csv(content)
        job.row_count_raw = raw_count
        job.row_count_clean = clean_count
        db.commit()
        logger.info("Job %d: %d raw -> %d clean rows",job_id, raw_count, clean_count)
        
        # Anomaly detection
        df = anomaly_detector.detect_anomalies(df)
        
        # LLM batch classification for uncategorised rows
        uncategorised_idx = df.index[df["category"] == "Uncategorised"].tolist()
        if uncategorised_idx:
            batch = (
                df.loc[uncategorised_idx,["merchant","amount","currency","notes"]].fillna("").to_dict("records")
            )
            
            categories, llm_failed = llm_service.classify_transactions_batch(batch)
            
            for batch_pos, df_idx in enumerate(uncategorised_idx):
                if batch_pos in categories:
                    df.at[df_idx,"llm_category"] = categories[batch_pos]
                    df.at[df_idx, "category"] = categories[batch_pos]
                else:
                    df.at[df_idx,"llm_failed"] = True
                    
            if llm_failed:
                logger.warning("Job %d: LLM classification failed for batch", job_id)
                
        # Persist transactions
        txn_objects: list[Transaction] = []
        for _, row in df.iterrows():
            
            
            is_anomaly = row.get("is_anomaly")
            llm_failed = row.get("llm_failed")
            
            if pd.isna(is_anomaly):
                is_anomaly = False
            else:
                is_anomaly = bool(is_anomaly)
                
            if pd.isna(llm_failed):
                llm_failed = False
            else:
                llm_failed = bool(llm_failed)
            
            txn_objects.append(
                Transaction(
                    job_id=job_id,
                    txn_id=_str_or_none(row.get("txn_id")),
                    date=row["date"],
                    merchant=str(row["merchant"]),
                    amount=float(row["amount"]),
                    currency=str(row["currency"]),
                    status=str(row["status"]),
                    category=str(row["category"]),
                    account_id=str(row["account_id"]),
                    notes=_str_or_none(row["notes"]),
                    is_anomaly=is_anomaly,
                    anomaly_reason=_str_or_none(row.get("anomaly_reason")),
                    llm_category=_str_or_none(row.get("llm_category")),
                    llm_failed=llm_failed
                )
            )
        db.bulk_save_objects(txn_objects)
        db.flush()

        # Compute aggregates for the LLM narative prompt
        inr_total = float(df.loc[df["currency"] == "INR","amount"].sum())
        usd_total = float(df.loc[df["currency"] == "USD", "amount"].sum())
        top_merchants: dict[str, float] = (
            df.groupby("merchant")["amount"]
            .sum()
            .nlargest(3)
            .round(2)
            .to_dict()
        )
        
        anomaly_count = int(df["is_anomaly"].sum())
        
        summary_input = {
            "total_spend_inr": round(inr_total, 2),
            "total_spend_usd": round(usd_total, 2),
            "top_merchants": top_merchants,
            "anomaly_count": anomaly_count,
            "transactions_count": clean_count,
            "status_breakdown": df["status"].value_counts().to_dict(),
            "category_breakdown": df.groupby("category")["amount"].sum().round(2).to_dict(),
        }
        
        # LLM narrative summary
        narrative_result, narrative_failed = llm_service.generate_narrative(summary_input)
        
        if narrative_result:
            summary = JobSummary(
                job_id=job_id,
                total_spend_inr=narrative_result.get("total_spend_inr",inr_total),
                total_spend_usd=narrative_result.get("total_spend_usd",usd_total),
                top_merchants=narrative_result.get("top_merchants", top_merchants),
                anomaly_count=narrative_result.get("anomaly_count", anomaly_count),
                narrative=narrative_result.get("narrative",""),
                risk_level=narrative_result.get("risk_level","low")
            )
        else:
            summary = JobSummary(
                job_id=job_id,
                total_spend_inr=inr_total,
                total_spend_usd=usd_total,
                top_merchants=top_merchants,
                anomaly_count=anomaly_count,
                narrative="LLM narrative unavailable. Summary computed from raw data.",
                risk_level=_compute_risk(anomaly_count)
            )
        db.add(summary)
    
        # Mark completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(tz=timezone.utc)
        db.commit()
        logger.info("Job %d completed successfully", job_id)
    
    except Exception as exc:
        logger.exception("Job %d pipeline failed - %s", job_id, exc)
        db.rollback()
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Job %d could not persist FAILED status", job_id)
        raise
    finally:
        db.close()

# helper functions

def _str_or_none(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() != "nan" else None

def _compute_risk(anomaly_count: int) -> str:
    if anomaly_count >= 5:
        return "high"
    if anomaly_count >= 1:
        return "medium"
    return "low"