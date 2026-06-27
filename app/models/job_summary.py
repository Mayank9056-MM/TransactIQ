from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

class JobSummary(Base):
    __tablename__ = "job_summaries"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )
    
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id",ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    
    total_spend_inr: Mapped[float] = mapped_column(
        default=0
    )
    
    total_spend_usd: Mapped[float] = mapped_column(
        default=0
    )
    
    top_merchants: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    
    anomaly_count: Mapped[int] = mapped_column(
        default=0
    )
    
    narrative: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    
    job: Mapped["Job"] = relationship(
        back_populates="summary"
    )