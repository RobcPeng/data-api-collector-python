import json
from fastapi import APIRouter
from app.core.config import settings
import redis
from app.models.events import RedisReq


router = APIRouter(prefix="/redis", tags=["redis"])
redis_r = redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.get("/test/redis")
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
     
@router.post("/test/redis/set")
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

@router.get("/test/redis/get")
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
