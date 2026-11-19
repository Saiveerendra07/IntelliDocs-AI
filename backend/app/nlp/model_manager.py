import os
from typing import Optional, Any
from backend.app.core.config import settings
from backend.app.core.logging import logger

_MODEL_MANAGER_INSTANCE = None


class ModelManager:
    """
    Centralized singleton manager for Hugging Face Transformers and SentenceTransformers.
    Implements lazy-loading and hardware acceleration fallback (CUDA -> CPU).
    """
    def __init__(self):
        self._summarizer = None
        self._embedding_model = None
        self._qa_model = None
        self._tokenizer = None
        self._device = None

    @property
    def device(self) -> str:
        if self._device is None:
            try:
                import torch
                if torch.cuda.is_available() and settings.TORCH_DEVICE.lower() == "cuda":
                    self._device = "cuda"
                else:
                    self._device = "cpu"
            except Exception:
                self._device = "cpu"
            logger.info(f"ModelManager initialized on device: {self._device}")
        return self._device

    def get_summarizer(self, model_name: Optional[str] = None):
        """
        Returns a cached Hugging Face summarization pipeline.
        Default: sshleifer/distilbart-cnn-12-6, fallback to t5-small.
        """
        if self._summarizer is not None:
            return self._summarizer

        target_model = model_name or settings.SUMMARIZATION_MODEL or "sshleifer/distilbart-cnn-12-6"
        logger.info(f"Loading summarization pipeline for {target_model}...")

        try:
            from transformers import pipeline
            device_id = 0 if self.device == "cuda" else -1
            self._summarizer = pipeline(
                "summarization",
                model=target_model,
                device=device_id,
                torch_dtype="auto" if self.device == "cuda" else None,
            )
            logger.info(f"Summarizer {target_model} loaded successfully.")
            return self._summarizer
        except Exception as e:
            logger.warning(f"Failed to load {target_model}: {e}. Attempting fallback to 't5-small'...")
            try:
                from transformers import pipeline
                self._summarizer = pipeline(
                    "summarization",
                    model="t5-small",
                    device=-1,
                )
                logger.info("Fallback summarizer 't5-small' loaded successfully.")
                return self._summarizer
            except Exception as e2:
                logger.error(f"Failed to load fallback summarizer: {e2}")
                raise

    def get_embedding_model(self, model_name: Optional[str] = None):
        """
        Returns cached SentenceTransformer model (default: all-MiniLM-L6-v2).
        """
        if self._embedding_model is not None:
            return self._embedding_model

        target_model = model_name or settings.EMBEDDING_MODEL or "all-MiniLM-L6-v2"
        logger.info(f"Loading SentenceTransformer: {target_model}...")
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(target_model, device=self.device)
            logger.info(f"SentenceTransformer {target_model} loaded successfully.")
            return self._embedding_model
        except Exception as e:
            logger.error(f"Failed to load embedding model {target_model}: {e}")
            raise


def get_model_manager() -> ModelManager:
    global _MODEL_MANAGER_INSTANCE
    if _MODEL_MANAGER_INSTANCE is None:
        _MODEL_MANAGER_INSTANCE = ModelManager()
    return _MODEL_MANAGER_INSTANCE
