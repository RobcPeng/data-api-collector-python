from re import S
from pydantic_settings import BaseSettings
from typing import Optional

from redis.utils import C

class Settings(BaseSettings):
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str 
    POSTGRES_DB: str
    DATABASE_URL: str
    POSTGRES_PORT: str
    
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_MAX_CONNECTION_LIFETIME: int
    NEO4J_MAX_CONNECTION_POOL_SIZE: int
    NEO4J_CONNECTION_TIMEOUT: int
    NEO4J_DATABASE: str
    
    
    DEBUG: bool = False
    PROJECT_NAME: str = "Data API Collector"
    REDIS_URL: str
    KAFKA_BOOTSTRAP_SERVERS: str
    API_V1_STR: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: str
    
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_API_KEY: str = "ollama"

    POSTGRES_PORT_EXTERNAL: str
    REDIS_PORT_EXTERNAL: str
    CADDY_HTTP_PORT: str
    CADDY_HTTPS_PORT: str

    MODEL_TYPE: str
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        

settings = Settings()