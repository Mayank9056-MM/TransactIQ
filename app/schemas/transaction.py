from datetime import date

from .base import BaseSchema

class TransactionResponse(BaseSchema):
    id: int
    
    txn_id: str | None
    
    date: date
    
    merchant: str
    
    amount: float
    
    currency: str
    
    status: str
    
    category: str
    
    account_id: str
    
    notes: str | None
    
    is_anomaly: bool
    
    anomaly_reason: str | None
    
    llm_category: str | None
    
    llm_failed: bool