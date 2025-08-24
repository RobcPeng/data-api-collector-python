from pydantic import BaseModel


class KafkaMessage(BaseModel):
    topic_name: str
    topic_message: str
    source: str