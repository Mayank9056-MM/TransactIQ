from .base import BaseSchema

class JobSummaryResponse(BaseSchema):
    total_spend_inr: float
    
    total_spend_usd: float
    
    top_merchants: dict
    
    anomaly_count: int
    
    narrative: str
    
    risk_level: str