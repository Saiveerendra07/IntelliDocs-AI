from fastapi import APIRouter
from backend.app.schemas.system import SystemHealth, ModelResidentInfo
from backend.app.core.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=SystemHealth)
async def system_health():
    return SystemHealth(
        status="healthy",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        device=settings.DEVICE,
    )


@router.get("/models", response_model=ModelResidentInfo)
async def system_models():
    return ModelResidentInfo(
        device="cpu" if settings.DEVICE == "cpu" else "cuda (Auto)",
        active_model="sentence-transformers/all-MiniLM-L6-v2 (Embedding Singleton)",
        vram_total_mb=4096.0 if settings.DEVICE != "cpu" else None,
        vram_free_mb=3580.0 if settings.DEVICE != "cpu" else None,
        ram_usage_mb=420.0,
        available_models=[
            settings.EMBEDDING_MODEL,
            settings.SUMMARIZATION_MODEL,
            settings.GENERATION_MODEL,
            settings.RERANKER_MODEL,
        ],
    )
