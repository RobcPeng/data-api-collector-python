# main.py - Parent directory main application
from fastapi import FastAPI
from app.core.config import settings

# Import routers from child directory
from app.api.endpoints import router as api_router

# Create main application
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
    description="Data API with multiple service integrations",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Include routers
app.include_router(api_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Data API is running",
        "version": "1.0.0",
        "services": ["data-sources", "kafka", "redis"],
        "documentation": "/docs",
        "endpoints": {
            "data_sources": "/data-sources/*",
            "kafka": "/kafka/*", 
            "redis": "/redis/*"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "data-api",
        "version": "1.0.0"
    }

