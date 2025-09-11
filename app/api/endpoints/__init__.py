from fastapi import APIRouter
from .data_sources import router as data_sources_router
from .kafka import router as kafka_router
from .redis import router as redis_router
from .neo4j import router as neo_data_sources_router
from .llms import router as llm_router
from .ollama_test import router as ollama_test_router
from .multimodal_ocr import router as multimodal_router
# Create main router that combines all endpoint routers
router = APIRouter(prefix="/api/v1")

# Include all the individual routers
router.include_router(data_sources_router)
router.include_router(neo_data_sources_router)
router.include_router(kafka_router)
router.include_router(redis_router)
router.include_router(llm_router)
router.include_router(ollama_test_router)
router.include_router(multimodal_router)



__all__ = ["router"]