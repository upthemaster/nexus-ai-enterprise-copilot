"""
Schemas for BM25 keyword search, Reciprocal Rank Fusion, and hybrid retrieval.

Why: Providing explicit schemas for hybrid query payloads and candidate debug metadata
ensures transparency into how vector and keyword retrievers contribute to final rankings.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RetrievalDebugInfo(BaseModel):
    """
    Observability breakdown detailing candidate performance in each individual retriever.
    
    Why: Required by Section 14 and Section 16 of the blueprint for debugging,
    latency/relevance analysis, and evaluation comparisons.
    """
    vector_rank: Optional[int] = Field(default=None, description="1-based rank in dense vector candidate pool")
    vector_score: Optional[float] = Field(default=None, description="Cosine similarity score from vector retriever")
    bm25_rank: Optional[int] = Field(default=None, description="1-based rank in sparse BM25 candidate pool")
    bm25_score: Optional[float] = Field(default=None, description="Raw BM25 Okapi term matching score")
    rrf_score: float = Field(description="Reciprocal Rank Fusion score: sum(1 / (k + rank))")


class BM25SearchRequest(BaseModel):
    """
    Query payload for sparse BM25 keyword search.
    """
    query: str = Field(min_length=1, description="Keyword search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of candidate chunks to retrieve")
    document_id: Optional[str] = Field(default=None, description="Optional document_id filter")


class BM25SearchResultItem(BaseModel):
    """
    Candidate chunk retrieved from BM25 sparse index.
    """
    chunk_id: str = Field(description="Identifier of the retrieved chunk")
    document_id: str = Field(description="Source document identifier")
    filename: str = Field(description="Source document display filename")
    page_number: int = Field(description="Source page number for citations")
    chunk_index: int = Field(description="Chunk sequence position")
    text: str = Field(description="Chunk text content")
    score: float = Field(description="Raw BM25 Okapi relevance score")


class BM25SearchResponse(BaseModel):
    """
    Response schema for BM25 keyword search.
    """
    query: str = Field(description="Echoed search query")
    results: List[BM25SearchResultItem] = Field(default_factory=list, description="Ranked BM25 matches")
    total_results: int = Field(description="Total chunks returned")


class HybridSearchRequest(BaseModel):
    """
    Query payload for hybrid retrieval combining vector and BM25 search via RRF.
    """
    query: str = Field(min_length=1, description="Natural language or keyword search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Final number of fused candidates to return")
    document_id: Optional[str] = Field(default=None, description="Optional document_id filter")
    candidate_multiplier: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Multiplier for initial candidate pools retrieved from each system before fusion"
    )


class HybridSearchResultItem(BaseModel):
    """
    Candidate chunk retrieved from hybrid fusion with source citations and debug metadata.
    """
    chunk_id: str = Field(description="Identifier of the retrieved chunk")
    document_id: str = Field(description="Source document identifier")
    filename: str = Field(description="Source document display filename")
    page_number: int = Field(description="Source page number for verifiable citations")
    chunk_index: int = Field(description="Chunk sequence position")
    text: str = Field(description="Passage text content")
    rrf_score: float = Field(description="Combined Reciprocal Rank Fusion score")
    debug: RetrievalDebugInfo = Field(description="Breakdown of vector and BM25 ranking contributions")


class HybridSearchResponse(BaseModel):
    """
    Response schema for hybrid retrieval.
    """
    query: str = Field(description="Echoed search query")
    results: List[HybridSearchResultItem] = Field(default_factory=list, description="Ranked fused results")
    total_results: int = Field(description="Number of fused results returned")

