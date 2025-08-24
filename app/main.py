from socket import timeout
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.core.config import settings
from confluent_kafka import Producer, Consumer
import redis

from app.models.events import KafkaMessage
from app.schemas.events import EventBase

app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG)
producer = Producer({'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS})
consumer = Consumer({'bootstrap.servers':settings.KAFKA_BOOTSTRAP_SERVERS, 
                     'group.id':"data-api-collector-test",
                     'auto.offset.reset':'earliest'})


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
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.set('test_key','Hello from FastAPI')
        value = r.get('test_key')
        info = r.info()
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
async def kafka_test_produce_message(request: KafkaMessage):
    try:
        event = EventBase( event_type =  "send-message", user_id = request.source, event_data = {"topic_name":request.topic_name, "topic_message":request.topic_message})
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
        print("ok")
        msg_count = 0
        for i in range (message_limit):
            msg = consumer.poll(timeout = 1.0)
            print(i)
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
    