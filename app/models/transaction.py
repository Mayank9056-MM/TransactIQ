from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text
) 
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

class Trasaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )
    
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id",ondelete="CASCADE"),
        nullable=False
    )
    
    txn_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    
    merchant: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    account_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    is_anomaly: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    anomaly_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    llm_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    llm_raw_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    llm_failed: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    job: Mapped["Job"] = relationship(
        back_populates="transactions"
    )