from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base

class RedisReq(BaseModel):
    key_store: str = Field(..., min_length=1, max_length=512)
    value: Any

    class Config:
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "key_store": "example_key",
                "value": [1, "string", {"nested": "object"}]
            }
        }

class KafkaMessage(BaseModel):
    topic_name: str = Field(..., min_length=1, max_length=255, pattern=r'^[a-zA-Z0-9._\-]+$')
    topic_message: str = Field(..., min_length=1, max_length=1048576)
    source: str = Field(..., min_length=1, max_length=255)
    
class KafkaEventLog(Base):
    __tablename__ = "kafka_event_logs"
    
    id = Column(Integer, primary_key = True, autoincrement=True)
    event_type = Column(String(255), nullable=False)
    user_id = Column(String(255))
    topic_name = Column(String(255), nullable=False)
    topic_message = Column(Text)
    created_at = Column(DateTime, default= func.now())
    
    
    def __repr__(self):
        return f"<KafkaEventLog(id={self.id}, topic={self.topic_name}, event_type={self.event_type})>"