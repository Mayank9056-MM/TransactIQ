from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.job import Job, JobStatus
from app.models.job_summary import JobSummary
from app.models.transaction import Transaction
from app.schemas.job import JobListResponse, JobResponse, JobStatusResponse
from app.schemas.results import JobResultsResponse, CategoryStat
from app.services.csv_processor import validate_columns
from app.workers.tasks import process_job

import pandas as pd
import io

router = APIRouter(prefix="/jobs", tags=["jobs"])

# POST /jobs/upload

@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
    summary="Upload a CSV file and enqueue a processing job"
)

def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted."
        )
        
    content = file.file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )
        
    # Validate columns before enqueuing
    
    try:
        df_peek = pd.read_csv(io.BytesIO(content), nrows=0)
        missing = validate_columns(df_peek)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"CSV missing required columns: {missing}"
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot parse CSV: {exc}"
        )
        
    # Persist file
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name=f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(content)

    # Create Job record
    job = Job(filename=file.filename, file_path=str(file_path))
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue Celery task
    process_job.delay(job.id)

    return {"job_id": job.id, "status": job.status, "filename": job.filename}

# GET /jobs/{job_id}/status 
@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Poll the status of a job"
)
def get_job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = _get_job_or_404(db, job_id)
    
    summary_data: dict | None = None
    
    if job.status == JobStatus.COMPLETED and job.summary:
        s = job.summary
        summary_data = {
            "row_count_clean": job.row_count_clean,
            "total_spend_inr": s.total_spend_inr,
            "total_spend_usd": s.total_spend_usd,
            "anomaly_count": s.anomaly_count,
            "risk_level": s.risk_level,
        }
    return JobStatusResponse(job_id=job.id, status=job.status, summary=summary_data)

# GET /jobs/{job_id}/results
@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    summary="Retrieve full results of a completed job"
)
def get_job_results(job_id: int, db: Session = Depends(get_db)) -> JobResultsResponse:
    job = _get_job_or_404(db, job_id)
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not completed yet (current status: {job.status})."
        )
        
    txns: list[Transaction] = (
        db.execute(select(Transaction).where(Transaction.job_id == job.id))
        .scalars()
        .all()
    )
    
    anomalies = [t for t in txns if t.is_anomaly]
    
    # Per-category aggregation
    category_breakdown: dict[str, CategoryStat] = {}
    for txn in txns:
        cat = txn.category or "Uncategorised"
        stat = category_breakdown.setdefault(
            cat, CategoryStat(total_amount=0.0, transaction_count=0)
        )
        stat.total_amount = round(stat.total_amount + txn.amount, 2)
        stat.transaction_count += 1
        
    from app.schemas.transaction import TransactionResponse
    from app.schemas.job_summary import JobSummaryResponse
    
    return JobResultsResponse(
        job_id=job.id,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        transactions=[TransactionResponse.model_validate(t) for t in txns],
        anomalies=[TransactionResponse.model_validate(t) for t in anomalies],
        category_breakdown=category_breakdown,
        summary=(
            JobSummaryResponse.model_validate(job.summary) if job.summary else None
        )
    )
    
# GET /jobs
@router.get(
    "",
    response_model=list[JobListResponse],
    summary="List all jobs, optionally filtered by status"
)
def list_jobs(
    status: JobStatus | None = Query(default=None, description="Filter by job status"),
    db: Session = Depends(get_db)
) -> list[JobListResponse]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    jobs = db.execute(stmt).scalars().all()
    return [JobListResponse.model_validate(j) for j in jobs]

# shared helper

def _get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )
    return job