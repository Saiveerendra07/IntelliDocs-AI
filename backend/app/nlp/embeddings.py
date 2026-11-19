from typing import List, Union
import numpy as np
from backend.app.nlp.model_manager import get_model_manager


class EmbeddingEngine:
    """
    Local embedding engine powered by SentenceTransformers (all-MiniLM-L6-v2).
    Generates 384-dimensional dense semantic vectors.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_manager = get_model_manager()
        self.model_name = model_name

    def embed_text(self, text: str) -> List[float]:
        """Encodes a single string into a 1D embedding vector."""
        model = self.model_manager.get_embedding_model(self.model_name)
        embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Encodes a batch of strings into normalized 2D embedding vectors."""
        if not texts:
            return []
        model = self.model_manager.get_embedding_model(self.model_name)
        embeddings = model.encode(texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
