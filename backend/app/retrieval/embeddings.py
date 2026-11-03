"""
Local embedding service utilizing SentenceTransformers.

Why: Running embeddings locally via `all-MiniLM-L6-v2` eliminates external API costs,
removes rate limit and network quota dependencies, and ensures high-speed batch
encoding directly on host hardware.
"""

import threading
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger("nexusai.embeddings")


class EmbeddingService:
    """
    Lazy-loaded singleton wrapper for SentenceTransformer embedding models.
    
    Why: Deferring PyTorch model loading until first invocation ensures fast
    application boot times and avoids redundant model allocations across threads.
    """
    _instance: Optional["EmbeddingService"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._model_name = settings.EMBEDDING_MODEL_NAME

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        """
        Thread-safe singleton accessor.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def model(self) -> SentenceTransformer:
        """
        Lazy-load the underlying SentenceTransformer model on demand.
        """
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info("Loading local embedding model: %s", self._model_name)
                    self._model = SentenceTransformer(self._model_name)
                    logger.info("Local embedding model loaded successfully.")
        return self._model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Compute dense vector embeddings for a batch of document chunk texts.
        
        Why: Using normalize_embeddings=True ensures inner-product and cosine distance
        calculations in ChromaDB are equivalent, improving similarity precision.
        """
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """
        Compute a dense vector embedding for a single search query string.
        """
        if not query or not query.strip():
            return []
        embedding = self.model.encode(
            query.strip(),
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return embedding.tolist()


# Global accessor function
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.get_instance()

