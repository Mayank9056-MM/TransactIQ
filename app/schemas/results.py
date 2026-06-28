from .base import BaseSchema
from .job_summary import JobSummaryResponse
from .transaction import TransactionResponse

class CategoryStat(BaseSchema):
    total_amount: float
    transaction_count: int
    
class JobResultsResponse(BaseSchema):
    job_id: int
    row_count_raw: int
    row_count_clean: int
    transactions: list[TransactionResponse]
    anomalies: list[TransactionResponse]
    category_breakdown: dict[str, CategoryStat]
    summary: JobSummaryResponse | None