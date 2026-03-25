from fastapi import APIRouter
from .data_sources import router as data_sources_router
from .kafka import router as kafka_router
from .redis import router as redis_router
from .neo4j import router as neo_data_sources_router
from .llms import router as llm_router
from .ollama_test import router as ollama_test_router
from .service_ocr import router as service_ocr_router
from .kafka_generators import router as kafka_generators_router
from .sled import neo4j_router as sled_neo4j_router
from .sled import postgres_router as sled_postgres_router
from .kafka_custom_generators import router as kafka_custom_generators_router
from .custom_generators import neo4j_router as custom_neo4j_router
from .custom_generators import postgres_router as custom_postgres_router
# Create main router that combines all endpoint routers
router = APIRouter(prefix="/api/v1")

# Include all the individual routers
router.include_router(data_sources_router)
router.include_router(neo_data_sources_router)
router.include_router(kafka_router)
router.include_router(kafka_custom_generators_router)  # must be before kafka_generators (path collision)
router.include_router(kafka_generators_router)
router.include_router(redis_router)
router.include_router(llm_router)
router.include_router(ollama_test_router)
router.include_router(service_ocr_router)
router.include_router(sled_neo4j_router)
router.include_router(sled_postgres_router)
router.include_router(custom_neo4j_router)
router.include_router(custom_postgres_router)



__all__ = ["router"]