"""
Search endpoints for vector, BM25, and hybrid retrieval.

Why: Exposes HTTP interfaces for semantic vector search, BM25 keyword search,
and hybrid Reciprocal Rank Fusion (RRF) search. Supports comparative evaluation
and fulfills Day 3 exit criteria.
"""

from fastapi import APIRouter, status
from app.schemas.chunk import VectorSearchRequest, VectorSearchResponse
from app.schemas.search import (
    BM25SearchRequest,
    BM25SearchResponse,
    HybridSearchRequest,
    HybridSearchResponse
)
from app.services.indexing_service import IndexingService

router = APIRouter()


@router.post(
    "/vector",
    response_model=VectorSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search",
    description="Queries indexed document chunks using dense embeddings and cosine similarity."
)
async def search_vector(request: VectorSearchRequest) -> VectorSearchResponse:
    """
    Execute semantic similarity search against indexed document chunks.
    """
    return IndexingService.search_similar_chunks(
        query=request.query,
        top_k=request.top_k,
        document_id=request.document_id
    )


@router.post(
    "/bm25",
    response_model=BM25SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="BM25 keyword search",
    description="Queries indexed document chunks using sparse BM25 token matching."
)
async def search_bm25(request: BM25SearchRequest) -> BM25SearchResponse:
    """
    Execute sparse BM25 keyword search against indexed document chunks.
    """
    return IndexingService.search_bm25(
        query=request.query,
        top_k=request.top_k,
        document_id=request.document_id
    )


@router.post(
    "/hybrid",
    response_model=HybridSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid RRF search",
    description="Fuses dense vector and sparse BM25 candidate pools using Reciprocal Rank Fusion (RRF)."
)
async def search_hybrid(request: HybridSearchRequest) -> HybridSearchResponse:
    """
    Execute hybrid retrieval combining dense semantic search and BM25 with RRF.
    """
    return IndexingService.search_hybrid(
        query=request.query,
        top_k=request.top_k,
        document_id=request.document_id,
        candidate_multiplier=request.candidate_multiplier
    )
