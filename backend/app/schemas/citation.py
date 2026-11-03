"""
Pydantic schemas for citation validation, source panel presentation, and source inspection.

Why: Fulfills Section 6.6 and Table 9 of the Master Blueprint:
- Preserving rich metadata for the UI Citation & Source Panel.
- Distinguishing direct quotations from paraphrases.
- Providing inspection payloads for GET /api/v1/citations/{chunk_id}.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SourcePanelItem(BaseModel):
    """
    Rich citation metadata prepared specifically for UI side panels and evidence inspection.
    """
    citation_index: int = Field(description="1-based numerical index corresponding to UI citation badges")
    document_id: str = Field(description="Source document identifier")
    filename: str = Field(description="Original document filename")
    page_number: int = Field(description="1-based physical page number")
    chunk_id: str = Field(description="Unique chunk identifier")
    snippet: str = Field(description="Context passage excerpt supporting the answer")
    relevance_score: Optional[float] = Field(default=None, description="Neural reranker logit score or RRF rank score")
    is_direct_quote: bool = Field(default=False, description="True if answer directly quotes verbatim text from this chunk")
    quote_span: Optional[str] = Field(default=None, description="Verbatim quote text excerpted directly in the answer")


class SourceInspectorResponse(BaseModel):
    """
    Full passage details returned by GET /api/v1/citations/{chunk_id}.
    """
    chunk_id: str = Field(description="Unique chunk identifier")
    document_id: str = Field(description="Source document identifier")
    filename: str = Field(description="Original document display filename")
    page_number: int = Field(description="Source page number")
    chunk_index: int = Field(description="Sequential chunk position within document")
    text: str = Field(description="Full text of the indexed chunk")
    character_count: int = Field(description="Total character count of passage")


class CitationValidationResult(BaseModel):
    """
    Result of server-side citation verification against retrieved passages.
    """
    valid_citations: List[SourcePanelItem] = Field(default_factory=list, description="Verified citations backed by actual chunks")
    discarded_chunk_ids: List[str] = Field(default_factory=list, description="Hallucinated or unsupplied chunk IDs discarded by server")

