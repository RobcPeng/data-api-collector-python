from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from confluent_kafka import Producer, Consumer
import json
from app.models.events import KafkaMessage, KafkaEventLog

app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG)
producer = Producer({'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS})
consumer = Consumer({'bootstrap.servers':settings.KAFKA_BOOTSTRAP_SERVERS, 
                     'group.id':"data-api-collector-test",
                     'auto.offset.reset':'earliest'})
 
@app.post("/test/kafka/producer/send-message")
async def kafka_test_produce_message(request: KafkaMessage, db: Session = Depends(get_db)):
    try:
        producer.produce(request.topic_name,request.topic_message)        
        kafka_event = KafkaEventLog(
            event_type =  "send-message", 
            user_id = request.source,
            topic_name = request.topic_name,
            topic_message = request.topic_message    
        )
        db.add(kafka_event)
        await db.commit()
        return {"status": "success", "topic": request.topic_name, "message": request.topic_message}
    except Exception as e:
         return {"status":"error", "message":str(e)} 
     
@app.post("/test/kafka/producer/send-message_old_flush")
async def kafka_test_produce_message_old(request: KafkaMessage, db: Session = Depends(get_db)):
    try:
        kafka_event = KafkaEventLog(
            event_type =  "send-message", 
            user_id = request.source,
            topic_name = request.topic_name,
            topic_message = request.topic_message    
        )
        db.add(kafka_event)
        db.commit()
        producer.produce(request.topic_name,request.topic_message)
        producer.flush() 
        return {"status": "success", "topic": request.topic_name, "message": request.topic_message}
    except Exception as e:
         return {"status":"error", "message":str(e)} 
    
@app.get("/test/kafka/consume/consume-message")
async def kafka_test_consume_message(topic_name: str, message_limit: int = 5):
    try:
        messages = []
        consumer.subscribe([topic_name])
        for i in range (message_limit):
            msg = consumer.poll(timeout = 1.0)
            if msg is None:
                continue
            if msg.error():
                messages.append({"error":str(msg.error())})
            else:
                messages.append({
                    "topic":msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "value": msg.value()
                })
        return {"status": "success", "messages": messages}
    except Exception as e:
         return {"status":"error", "message":str(e)} 
     
@app.get("/test/events/kafka")
async def get_kafka_events(
    skip: int = 0,
    limit: int = 100,
    topic_name: str = None,
    user_id: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(KafkaEventLog)
    
    # Apply filters if provided
    if topic_name:
        query = query.filter(KafkaEventLog.topic_name == topic_name)
    if user_id:
        query = query.filter(KafkaEventLog.user_id == user_id)
    
    # Order by most recent first
    query = query.order_by(KafkaEventLog.created_at.desc())
    
    # Get total count before applying limit
    total_count = query.count()
    
    # Apply pagination
    events = query.offset(skip).limit(limit).all()
    
    return {
        "total": total_count,
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "topic_name": event.topic_name,
                "message": event.topic_message,
                "timestamp": event.created_at.isoformat() if event.created_at else None
            }
            for event in events
        ]
    }
    