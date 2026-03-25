"""
EXPERIMENTAL: Custom Kafka generator proxy.
Lets users POST a JSON column spec (mapping to dbldatagen's withColumn API)
to create ad-hoc Kafka streaming generators.
"""
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/kafka/generators/custom", tags=["kafka-custom-generators", "experimental"])

SPARK_GENERATOR_URL = "http://spark-generator:8003"


async def _proxy_get(path: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(f"{SPARK_GENERATOR_URL}{path}")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


async def _proxy_post(path: str, body: dict | None = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(f"{SPARK_GENERATOR_URL}{path}", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


async def _proxy_delete(path: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.delete(f"{SPARK_GENERATOR_URL}{path}")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Spark generator service is unavailable.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/health")
async def custom_health():
    return await _proxy_get("/custom/health")


@router.post("/validate")
async def validate_spec(request: dict):
    """Validate a custom generator spec without starting it."""
    return await _proxy_post("/custom/validate", request)


@router.post("/start")
async def start_custom(request: dict):
    """Start a custom generator from a JSON column specification."""
    return await _proxy_post("/custom/start", request)


@router.post("/{generator_id}/stop")
async def stop_custom(generator_id: str):
    return await _proxy_post(f"/custom/{generator_id}/stop")


@router.get("")
async def list_custom():
    return await _proxy_get("/custom")


@router.get("/{generator_id}")
async def get_custom(generator_id: str):
    return await _proxy_get(f"/custom/{generator_id}")


@router.get("/{generator_id}/spec")
async def get_custom_spec(generator_id: str):
    """Get the column spec for a custom generator."""
    return await _proxy_get(f"/custom/{generator_id}/spec")


@router.delete("/cleanup")
async def cleanup_custom():
    return await _proxy_delete("/custom/cleanup")
