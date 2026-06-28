# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )
    
    # Database
    DATABASE_URL: str = "postgresql+psycopg://transactiq:transactiq@db:5432/transactiq"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # File storage
    UPLOAD_DIR: str = "/app/uploads"
    
    DEBUG: bool = False
    

    
settings = Settings()