from re import S
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str 
    POSTGRES_DB: str
    DATABASE_URL: str
    POSTGRES_PORT: str
    NEO4J_PASSWORD: str
    
    DEBUG: bool = False
    PROJECT_NAME: str = "Data API Collector"
    REDIS_URL: str
    KAFKA_BOOTSTRAP_SERVERS: str
    API_V1_STR: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: str
    
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()