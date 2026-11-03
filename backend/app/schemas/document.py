"""
Document ingestion schemas for request validation and response serialization.

Why: Defining clear, typed models ensures that API responses adhere strictly
to the contract defined in Section 6.1 and Section 9 of the NexusAI blueprint.
"""

from typing import List
from pydantic import BaseModel, Field


class PageExtraction(BaseModel):
    """
    Extracted textual content and structural metadata for an individual page or block.
    
    Why: Preserving page_number at the ingestion boundary allows downstream
    chunking, vector indexing, and LLM citations to accurately link back to
    precise source locations.
    """
    page_number: int = Field(description="1-based index of the page or section block")
    text: str = Field(description="Normalized extracted textual content")
    character_count: int = Field(description="Total characters extracted from this page/block")


class DocumentUploadResponse(BaseModel):
    """
    Standard response payload for successful document ingestion and indexing.
    
    Why: Provides immediate feedback to the caller regarding the internal document_id,
    parsed pages, total characters, indexable chunk count, content hash, and quality warnings.
    """
    document_id: str = Field(description="Unique internal identifier assigned to the document (UUID4)")
    filename: str = Field(description="Sanitized display filename of the uploaded document")
    file_type: str = Field(description="Detected document format (e.g., pdf, docx, txt)")
    status: str = Field(default="processed", description="Processing outcome (processed, already_indexed, warning)")
    extracted_pages: List[PageExtraction] = Field(
        default_factory=list,
        description="List of extracted text chunks grouped by page or paragraph section"
    )
    character_count: int = Field(description="Sum of all characters extracted across all pages")
    chunk_count: int = Field(default=0, description="Total number of indexable chunks created and stored in vector index")
    content_hash: str = Field(default="", description="SHA-256 hash of document text used for deduplication")
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during extraction (e.g., near-empty content)"
    )


class DocumentSummaryItem(BaseModel):
    """
    Summary representation of an indexed document for dashboard and documents view.
    """
    id: str = Field(description="Unique internal document UUID")
    filename: str = Field(description="Display filename of the document")
    file_type: str = Field(description="File extension format (pdf, docx, txt)")
    content_hash: str = Field(default="", description="SHA-256 hash of document text")
    status: str = Field(default="indexed", description="Ingestion status (indexed, indexing, failed)")
    chunk_count: int = Field(default=0, description="Total indexed text chunks")
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str = Field(description="ISO 8601 last update timestamp")


class DocumentListResponse(BaseModel):
    """
    Paginated or full list of registered documents.
    """
    total: int = Field(description="Total count of registered documents")
    documents: List[DocumentSummaryItem] = Field(
        default_factory=list,
        description="List of document summary items"
    )

