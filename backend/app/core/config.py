from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    APP_NAME: str = "IntelliDocs AI"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/intellidocs"

    # Security & Auth
    SECRET_KEY: str = "default_development_secret_key_change_me_in_production_environment"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Storage & Upload Limits
    MAX_UPLOAD_MB: int = 50
    STORAGE_DIR: str = "backend/storage"
    CHROMA_PERSIST_DIR: str = "backend/storage/chroma"

    # OCR Settings
    TESSERACT_CMD: str = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

    # Hardware & NLP Model Config
    DEVICE: str = "auto"
    TORCH_DEVICE: str = "cpu"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    SUMMARIZATION_MODEL: str = "sshleifer/distilbart-cnn-12-6"
    GENERATION_MODEL: str = "google/flan-t5-base"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ENABLE_RERANKER: bool = False

    # LLM Provider (local | gemini | openai)
    LLM_PROVIDER: str = "local"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
