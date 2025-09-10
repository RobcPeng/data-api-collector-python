from fastapi import APIRouter
from .data_sources import router as data_sources_router
from .kafka import router as kafka_router
from .redis import router as redis_router

# Create main router that combines all endpoint routers
router = APIRouter(prefix="/api/v1")

# Include all the individual routers
router.include_router(data_sources_router)
router.include_router(kafka_router)
router.include_router(redis_router)

__all__ = ["router"]