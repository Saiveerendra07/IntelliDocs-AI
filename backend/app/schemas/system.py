from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SystemHealth(BaseModel):
    status: str = "healthy"
    app: str
    version: str
    environment: str
    device: str


class ModelResidentInfo(BaseModel):
    device: str
    active_model: Optional[str] = None
    vram_total_mb: Optional[float] = None
    vram_free_mb: Optional[float] = None
    ram_usage_mb: Optional[float] = None
    available_models: List[str] = []
