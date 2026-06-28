# app/models/job.py

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

class JobStatus(str,Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    status: Mapped[JobStatus] = mapped_column(
        SqlEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False
    )
    
    row_count_raw: Mapped[int] = mapped_column(Integer, default=0)

    row_count_clean: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    summary: Mapped["JobSummary | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False
    )
   