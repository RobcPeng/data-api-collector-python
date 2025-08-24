from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Dict

class EventBase(BaseModel):
    event_type: str
    user_id: str | None = None
    session_id: str | None = None
    event_data: Dict[str, any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        arbitrary_types_allowed=True