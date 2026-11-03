"""
Hybrid retrieval with Reciprocal Rank Fusion (RRF).

Why: Combining dense vector search and sparse BM25 keyword search covers both
semantic understanding and exact keyword precision. Reciprocal Rank Fusion (RRF)
combines their ranked results without requiring brittle score calibration or normalization.
"""

import logging
from typing import List, Dict, Optional, Tuple

from app.core.config import settings
from app.schemas.search import (
    HybridSearchResultItem,
    RetrievalDebugInfo,
    BM25SearchResultItem
)
from app.schemas.chunk import VectorSearchResultItem
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager
from app.retrieval.embeddings import get_embedding_service

logger = logging.getLogger("nexusai.hybrid")


class HybridRetriever:
    """
    Executes hybrid retrieval by merging dense vector and sparse BM25 candidates via RRF.
    """

    @classmethod
    def retrieve(
        cls,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        candidate_multiplier: int = 2,
        rrf_k: int = settings.RRF_K
    ) -> List[HybridSearchResultItem]:
        """
        Execute dense vector retrieval and sparse BM25 search, fusing results via RRF.
        
        Args:
            query: User search query.
            top_k: Number of final fused passages to return.
            document_id: Optional document scope filter.
            candidate_multiplier: Multiplier for initial candidate pools (e.g. 2x top_k).
            rrf_k: Smoothing constant for RRF formula (default 60).
            
        Returns:
            List[HybridSearchResultItem] ordered by descending RRF score with full debug metadata.
        """
        # Step 1: Determine candidate pool size (retrieve wider candidate pool for fusion)
        candidate_k = min(50, max(top_k * candidate_multiplier, 10))

        # Step 2: Retrieve dense vector candidates
        vector_store = get_vector_store()
        embedding_service = get_embedding_service()
        query_embedding = embedding_service.embed_query(query)
        vector_candidates: List[VectorSearchResultItem] = vector_store.query_similar(
            query_embedding=query_embedding,
            top_k=candidate_k,
            document_id=document_id
        )

        # Step 3: Retrieve sparse BM25 keyword candidates
        bm25_manager = get_bm25_manager()
        bm25_candidates: List[BM25SearchResultItem] = bm25_manager.query(
            query=query,
            top_k=candidate_k,
            document_id=document_id
        )

        # Step 4: Apply Reciprocal Rank Fusion (RRF)
        # Formula: score(d) = sum(1 / (k + rank(d)))
        rrf_scores: Dict[str, float] = {}
        debug_records: Dict[str, Dict] = {}
        chunk_payloads: Dict[str, Dict] = {}

        # Process Vector Candidates
        for rank, item in enumerate(vector_candidates, start=1):
            chunk_id = item.chunk_id
            rrf_increment = 1.0 / (rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_increment

            if chunk_id not in debug_records:
                debug_records[chunk_id] = {
                    "vector_rank": rank,
                    "vector_score": item.score,
                    "bm25_rank": None,
                    "bm25_score": None,
                }
                chunk_payloads[chunk_id] = {
                    "document_id": item.document_id,
                    "filename": item.filename,
                    "page_number": item.page_number,
                    "chunk_index": item.chunk_index,
                    "text": item.text
                }
            else:
                debug_records[chunk_id]["vector_rank"] = rank
                debug_records[chunk_id]["vector_score"] = item.score

        # Process BM25 Candidates
        for rank, item in enumerate(bm25_candidates, start=1):
            chunk_id = item.chunk_id
            rrf_increment = 1.0 / (rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_increment

            if chunk_id not in debug_records:
                debug_records[chunk_id] = {
                    "vector_rank": None,
                    "vector_score": None,
                    "bm25_rank": rank,
                    "bm25_score": item.score,
                }
                chunk_payloads[chunk_id] = {
                    "document_id": item.document_id,
                    "filename": item.filename,
                    "page_number": item.page_number,
                    "chunk_index": item.chunk_index,
                    "text": item.text
                }
            else:
                debug_records[chunk_id]["bm25_rank"] = rank
                debug_records[chunk_id]["bm25_score"] = item.score

        # Step 5: Sort merged candidates by RRF score descending
        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True
        )

        # Slice to requested top_k
        top_chunk_ids = sorted_chunk_ids[:top_k]

        fused_results: List[HybridSearchResultItem] = []
        for cid in top_chunk_ids:
            score = round(rrf_scores[cid], 6)
            dbg = debug_records[cid]
            dbg_info = RetrievalDebugInfo(
                vector_rank=dbg["vector_rank"],
                vector_score=dbg["vector_score"],
                bm25_rank=dbg["bm25_rank"],
                bm25_score=dbg["bm25_score"],
                rrf_score=score
            )
            payload = chunk_payloads[cid]
            fused_results.append(
                HybridSearchResultItem(
                    chunk_id=cid,
                    document_id=payload["document_id"],
                    filename=payload["filename"],
                    page_number=payload["page_number"],
                    chunk_index=payload["chunk_index"],
                    text=payload["text"],
                    rrf_score=score,
                    debug=dbg_info
                )
            )

        logger.info(
            "Hybrid retrieval: query='%s', dense_hits=%d, sparse_hits=%d, fused=%d",
            query,
            len(vector_candidates),
            len(bm25_candidates),
            len(fused_results)
        )
        return fused_results

