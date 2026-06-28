from datetime import datetime
from enum import Enum

from .base import BaseSchema

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    
class JobCreate(BaseSchema):
    filename: str
    
class JobResponse(BaseSchema):
    id: int
    
    filename: str
    
    status: JobStatus
    
    row_count_raw: int
    
    row_count_clean: int
    
    error_message: str | None
    
    created_at: datetime
    
    completed_at: datetime | None
    
class JobStatusResponse(BaseSchema):
    job_id: int
    
    status: JobStatus
    
    summary: dict | None = None
    
class JobListResponse(BaseSchema):
    id: int
    
    filename: str
    
    status: JobStatus
    
    row_count_raw: int
    
    created_at: datetime