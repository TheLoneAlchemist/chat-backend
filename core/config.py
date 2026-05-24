from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Chat API"
    debug: bool = False
    
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = (
    "http://localhost:8000","*")
    
    # Limits
    rate_limit_msg_per_sec: float = 0.5
    max_message_length: int = 2000
    
    # Firebase (optional, for push later)
    firebase_credentials_path: str | None = None
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()