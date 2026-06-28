from datetime import datetime

from .base import BaseSchema

class MessageResponse(BaseSchema):
    message: str
    
class ErrorResponse(BaseSchema):
    detail: str
    
class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime | None = None