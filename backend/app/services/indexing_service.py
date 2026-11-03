"""
Indexing and retrieval orchestration service.

Why: Coordinates the end-to-end transformation of extracted document pages into
indexable chunks, vector embeddings, persistent ChromaDB storage, and sparse BM25 indexing.
Also orchestrates vector, BM25, and hybrid RRF retrieval.
"""

import logging
from typing import List, Tuple, Optional

from app.schemas.document import PageExtraction
from app.schemas.chunk import VectorSearchResponse
from app.schemas.search import (
    BM25SearchResponse,
    HybridSearchResponse
)
from app.ingestion.chunker import chunk_extracted_pages, compute_content_hash
from app.retrieval.embeddings import get_embedding_service
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger("nexusai.indexing")


class IndexingService:
    """
    Orchestrates chunking, dual-indexing (ChromaDB + BM25), deduplication, and hybrid search.
    """

    @classmethod
    def index_document(
        cls,
        document_id: str,
        filename: str,
        pages: List[PageExtraction]
    ) -> Tuple[int, str, bool]:
        """
        Chunk and dual-index extracted pages into persistent ChromaDB and BM25 index.
        
        Returns:
            Tuple[int, str, bool]: (chunk_count, content_hash, is_already_indexed)
        """
        content_hash = compute_content_hash(pages)
        vector_store = get_vector_store()
        bm25_manager = get_bm25_manager()

        # Idempotency check: avoid redundant re-embedding if document hash exists in either store
        if vector_store.is_document_indexed(content_hash) or bm25_manager.is_document_indexed(content_hash):
            logger.info("Document with content_hash=%s is already indexed. Skipping.", content_hash)
            existing_chunks = chunk_extracted_pages(document_id, filename, pages)
            return len(existing_chunks), content_hash, True

        # Generate structural chunks
        chunks = chunk_extracted_pages(document_id, filename, pages)
        if not chunks:
            logger.warning("No chunks generated for document_id=%s (empty content).", document_id)
            return 0, content_hash, False

        # Step A: Local dense embeddings & ChromaDB upsert
        embedding_service = get_embedding_service()
        texts = [chunk.text for chunk in chunks]
        embeddings = embedding_service.embed_documents(texts)
        upserted_count = vector_store.upsert_chunks(chunks=chunks, embeddings=embeddings)

        # Step B: Sparse BM25 keyword index addition & persistence
        bm25_manager.add_chunks(chunks)

        logger.info(
            "Dual-indexed document_id=%s: %d chunks added to ChromaDB and BM25.",
            document_id,
            upserted_count
        )
        return upserted_count, content_hash, False

    @classmethod
    def search_similar_chunks(
        cls,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> VectorSearchResponse:
        """
        Perform semantic vector similarity search against ChromaDB.
        """
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        query_embedding = embedding_service.embed_query(query)
        results = vector_store.query_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            document_id=document_id
        )

        return VectorSearchResponse(
            query=query,
            results=results,
            total_results=len(results)
        )

    @classmethod
    def search_bm25(
        cls,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> BM25SearchResponse:
        """
        Perform sparse BM25 keyword search.
        """
        bm25_manager = get_bm25_manager()
        results = bm25_manager.query(
            query=query,
            top_k=top_k,
            document_id=document_id
        )
        return BM25SearchResponse(
            query=query,
            results=results,
            total_results=len(results)
        )

    @classmethod
    def search_hybrid(
        cls,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        candidate_multiplier: int = 2
    ) -> HybridSearchResponse:
        """
        Perform hybrid retrieval combining vector and BM25 candidates via Reciprocal Rank Fusion.
        """
        fused_results = HybridRetriever.retrieve(
            query=query,
            top_k=top_k,
            document_id=document_id,
            candidate_multiplier=candidate_multiplier
        )
        return HybridSearchResponse(
            query=query,
            results=fused_results,
            total_results=len(fused_results)
        )
