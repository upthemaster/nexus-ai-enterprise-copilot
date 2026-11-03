"""
Schemas for document chunking, metadata attachment, and vector similarity search.

Why: Providing strongly typed schemas for chunk data structures and vector query
results guarantees strict serialization boundaries between ingestion, vector storage,
and API responses.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """
    Metadata associated with each individual document chunk.
    
    Why: Preserving document_id, filename, page_number, and chunk_index enables
    accurate, verifiable citations in downstream LLM answer generation.
    """
    document_id: str = Field(description="Internal unique document identifier (UUID)")
    filename: str = Field(description="Sanitized display filename of the source document")
    page_number: int = Field(description="1-based page or paragraph section index")
    chunk_index: int = Field(description="0-based sequential index of the chunk within the document")
    content_hash: str = Field(description="SHA-256 hash of the complete document text for deduplication")


class DocumentChunk(BaseModel):
    """
    Represents an atomic text chunk ready for vector embedding and storage.
    """
    chunk_id: str = Field(description="Unique deterministic chunk identifier")
    text: str = Field(description="Text content of the chunk")
    metadata: ChunkMetadata = Field(description="Structural metadata for citation and filtering")


class VectorSearchRequest(BaseModel):
    """
    Query payload for semantic vector search across indexed document chunks.
    """
    query: str = Field(min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of candidate chunks to retrieve")
    document_id: Optional[str] = Field(default=None, description="Optional document_id filter to scope search")


class VectorSearchResultItem(BaseModel):
    """
    An individual retrieved candidate chunk with relevance score and source metadata.
    """
    chunk_id: str = Field(description="Identifier of the retrieved chunk")
    document_id: str = Field(description="Source document identifier")
    filename: str = Field(description="Source document display filename")
    page_number: int = Field(description="Source page number for verifiable citations")
    chunk_index: int = Field(description="Chunk sequence position")
    text: str = Field(description="Passage text content")
    score: float = Field(description="Cosine similarity score (higher is more similar)")


class VectorSearchResponse(BaseModel):
    """
    Response schema for vector similarity search.
    """
    query: str = Field(description="Echoed search query")
    results: List[VectorSearchResultItem] = Field(
        default_factory=list,
        description="Ranked list of top matching chunks"
    )
    total_results: int = Field(description="Number of candidate chunks returned")

