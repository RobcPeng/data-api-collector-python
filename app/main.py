import json
from socket import timeout
from typing import Dict
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.core.config import settings
from confluent_kafka import Producer, Consumer
import redis
import json
from app.models.events import KafkaMessage, KafkaEventLog, RedisReq
from app.schemas.events import EventBase

app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG)
producer = Producer({'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS})
consumer = Consumer({'bootstrap.servers':settings.KAFKA_BOOTSTRAP_SERVERS, 
                     'group.id':"data-api-collector-test",
                     'auto.offset.reset':'earliest'})
redis_r = redis.from_url(settings.REDIS_URL, decode_responses=True)



@app.get("/test/orm")
async def test_orm_connection(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT version() as db_version"))
        row = result.fetchone()
        return {
            "status" : "success",
            "connection_type" : "SQLAlchemy ORM",
            "database_version": row.db_version
        }
    except Exception as e:
        return {"status":"error", "message":str(e)}
    
@app.get("/test/raw/sql")
async def test_raw_sql():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database() as current_db, now() as current_time"))
            row = result.fetchone()
            return {
                "status":"Success",
                "connection_type":"Raw SQL",
                "current_database":row.current_db,
                "current_time": str(row.current_time)
            }
    except Exception as e:
         return {"status":"error", "message":str(e)} 
     
     
@app.get("/test/connection-info")
async def connection_info():
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in_connections": pool.checkedin(),
        "checked_out_connections": pool.checkedout(),
        "total_connections": pool.size() + pool.checkedout()
    }
    
@app.get("/test/redis")
async def test_redis():
    try:
        redis_r.set('test_key','Hello from FastAPI')
        value = redis_r.get('test_key')
        info = redis_r.info()
        return {
            "status": "success",
            "message": str(value),
            "version": info["redis_version"],
            "connected_clients": info["connected_clients"],
            "used_memory_human": info["used_memory_human"]
        }
    except Exception as e:
         return {"status":"error", "message":str(e)} 
     
@app.post("/test/redis/set")
async def set_redis(request: RedisReq):
    try:
        if isinstance(request.value, (dict, list, tuple)):
            serialized_value = json.dumps(request.value)
        else:
            # For primitive types, convert to string if needed
            serialized_value = request.value
        redis_r.set(request.key_store,serialized_value)
        info = redis_r.info()
        return {
            "status": "success",
            "version": info["redis_version"],
            "connected_clients": info["connected_clients"],
            "used_memory_human": info["used_memory_human"]
        }
    except Exception as e:
         return {"status":"error", "message":str(e)} 

@app.get("/test/redis/get")
async def get_redis(key_store: str):
    try:
        value = redis_r.get(key_store)
        info = redis_r.info()
        return {
            "status": "success",
            "message": str(value),
            "version": info["redis_version"],
            "connected_clients": info["connected_clients"],
            "used_memory_human": info["used_memory_human"]
        }
    except Exception as e:
         return {"status":"error", "message":str(e)} 
 
@app.post("/test/kafka/producer/send-message")
async def kafka_test_produce_message(request: KafkaMessage, db: Session = Depends(get_db)):
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
    