import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/kafka/generators", tags=["kafka-generators"])

SPARK_GENERATOR_URL = "http://spark-generator:8003"


async def _proxy_get(path: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{SPARK_GENERATOR_URL}{path}")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


async def _proxy_post(path: str, body: dict | None = None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{SPARK_GENERATOR_URL}{path}", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


async def _proxy_delete(path: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(f"{SPARK_GENERATOR_URL}{path}")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/start")
async def start_generator(request: dict):
    """Start a streaming data generator that produces synthetic data to Kafka."""
    return await _proxy_post("/generators/start", request)


@router.post("/{generator_id}/stop")
async def stop_generator(generator_id: str):
    """Stop a running generator."""
    return await _proxy_post(f"/generators/{generator_id}/stop")


@router.get("")
async def list_generators():
    """List all generators and their status."""
    return await _proxy_get("/generators")


@router.get("/{generator_id}")
async def get_generator(generator_id: str):
    """Get status of a specific generator."""
    return await _proxy_get(f"/generators/{generator_id}")


@router.delete("/cleanup")
async def cleanup_generators():
    """Remove all completed/stopped/errored generators from the list."""
    return await _proxy_delete("/generators/cleanup")
