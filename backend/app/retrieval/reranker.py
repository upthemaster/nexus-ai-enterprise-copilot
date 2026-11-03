"""
Cross-Encoder second-stage passage reranker.

Why: First-stage hybrid retrieval (Bi-encoder embeddings + BM25) retrieves a broad candidate
pool (e.g. 10-20 passages). A Cross-Encoder applies full joint self-attention over [query, passage]
pairs to capture token-level semantic interactions, significantly improving Context Precision
and NDCG before presenting context to the LLM.
"""

import logging
from typing import List, Optional
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.schemas.search import HybridSearchResultItem
from app.schemas.chat import RerankedPassage

logger = logging.getLogger("nexusai.reranker")


class CrossEncoderReranker:
    """
    Singleton service for cross-encoder reranking.
    """
    _instance: Optional["CrossEncoderReranker"] = None

    def __init__(self, model_name: str = settings.RERANKER_MODEL_NAME):
        self.model_name = model_name
        logger.info("Loading Cross-Encoder model: %s", model_name)
        self.model = CrossEncoder(model_name)
        logger.info("Cross-Encoder model loaded successfully")

    @classmethod
    def get_instance(cls) -> "CrossEncoderReranker":
        """
        Thread-safe singleton accessor for CrossEncoderReranker.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def rerank(
        self,
        query: str,
        candidates: List[HybridSearchResultItem],
        top_k: int = settings.RERANKER_TOP_K
    ) -> List[RerankedPassage]:
        """
        Score query-passage pairs jointly and return the top-K highest scoring passages.
        
        Args:
            query: The user's search query or question.
            candidates: Retrieved candidate chunks from first-stage hybrid retrieval.
            top_k: Number of top reranked passages to retain.
            
        Returns:
            List of RerankedPassage items ordered by descending cross-encoder relevance score.
        """
        if not candidates:
            return []

        # Prepare (query, text) pairs for the cross-encoder
        pairs = [[query, candidate.text] for candidate in candidates]

        # Compute cross-attention relevance logits
        scores = self.model.predict(pairs)

        # Build scored passage list
        scored_passages: List[RerankedPassage] = []
        for i, (candidate, score) in enumerate(zip(candidates, scores)):
            passage = RerankedPassage(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                filename=candidate.filename,
                page_number=candidate.page_number,
                chunk_index=candidate.chunk_index,
                text=candidate.text,
                rerank_score=float(score),
                original_hybrid_rank=i + 1,
                rrf_score=candidate.rrf_score,
            )
            scored_passages.append(passage)

        # Sort descending by cross-encoder score
        scored_passages.sort(key=lambda p: p.rerank_score, reverse=True)

        return scored_passages[:top_k]

    @staticmethod
    def fallback_passthrough(
        candidates: List[HybridSearchResultItem],
        top_k: int = settings.RERANKER_TOP_K
    ) -> List[RerankedPassage]:
        """
        Bypasses cross-encoder computation when reranking is disabled, preserving RRF ranking.
        """
        passages: List[RerankedPassage] = []
        for i, candidate in enumerate(candidates[:top_k]):
            passages.append(
                RerankedPassage(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    filename=candidate.filename,
                    page_number=candidate.page_number,
                    chunk_index=candidate.chunk_index,
                    text=candidate.text,
                    rerank_score=candidate.rrf_score,
                    original_hybrid_rank=i + 1,
                    rrf_score=candidate.rrf_score,
                )
            )
        return passages


def get_reranker() -> CrossEncoderReranker:
    """
    Factory function returning the singleton CrossEncoderReranker.
    """
    return CrossEncoderReranker.get_instance()

