import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Menu Extractor API"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
