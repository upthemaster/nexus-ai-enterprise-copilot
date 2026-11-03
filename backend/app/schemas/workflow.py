"""
Pydantic schemas for LangGraph workflows, document summarization, and risk extraction.

Why: Explicitly typing workflow inputs and outputs guarantees contract safety across
FastAPI routes, LangGraph node transitions, and client consumers.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.schemas.chat import Citation

WorkflowType = Literal["auto", "qa", "summarize", "extract_risks"]
RiskSeverity = Literal["HIGH", "MEDIUM", "LOW"]


class WorkflowRequest(BaseModel):
    """
    Unified entrypoint request for LangGraph workflow execution.
    """
    query: str = Field(..., min_length=1, max_length=2000, description="User question or workflow directive")
    document_id: Optional[str] = Field(None, description="Optional target document ID for document-scoped workflows")
    workflow_type: WorkflowType = Field("auto", description="Explicit workflow type, or 'auto' for heuristic intent routing")
    top_k: int = Field(5, ge=1, le=20, description="Maximum evidence candidates to retrieve")


class WorkflowResponse(BaseModel):
    """
    Unified execution response for LangGraph workflows.
    """
    workflow_type: str = Field(..., description="Resolved workflow path ('qa', 'summarize', or 'extract_risks')")
    query: str = Field(..., description="Original user prompt or directive")
    document_id: Optional[str] = Field(None, description="Target document ID if scoped")
    result: str = Field(..., description="Final synthesized answer, summary, or report")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Typed breakdown (e.g. parsed risks, summary sections)")
    citations: List[Citation] = Field(default_factory=list, description="Validated citations mapped to verified evidence chunks")
    insufficient_evidence: bool = Field(False, description="True if evidence was missing or below relevance threshold")
    execution_route: List[str] = Field(default_factory=list, description="Sequential path of graph nodes traversed")
    timing_ms: float = Field(0.0, description="Total execution duration in milliseconds")


class DocumentSummarizeRequest(BaseModel):
    """
    Request payload for single-document summarization.
    """
    focus: Optional[str] = Field(None, description="Optional thematic focus (e.g. 'compliance obligations', 'pricing')")


class DocumentSummarizeResponse(BaseModel):
    """
    Response schema for document summarization.
    """
    document_id: str = Field(..., description="UUID of the summarized document")
    summary: str = Field(..., description="Full text summary synthesized from document evidence")
    executive_summary: Optional[str] = Field(None, description="High-level executive overview")
    key_findings: List[str] = Field(default_factory=list, description="Bullet points of key findings")
    action_items: List[str] = Field(default_factory=list, description="Identified action items or requirements")
    citations: List[Citation] = Field(default_factory=list, description="Verifiable citations supporting the summary")
    execution_route: List[str] = Field(default_factory=list, description="Graph path traversed")
    timing_ms: float = Field(0.0, description="Execution time in milliseconds")


class RiskItem(BaseModel):
    """
    Structured risk or liability finding extracted from enterprise documents.
    """
    risk_id: str = Field(..., description="Unique risk identifier (e.g. 'RISK-01')")
    category: str = Field(..., description="Risk category (e.g. 'Operational', 'Compliance', 'Financial', 'Legal')")
    severity: RiskSeverity = Field("MEDIUM", description="Assessed severity level")
    description: str = Field(..., description="Concise explanation of the identified risk")
    mitigation: Optional[str] = Field(None, description="Recommended mitigation or safeguard")
    source_chunk_id: Optional[str] = Field(None, description="Evidence chunk identifier")
    page_number: Optional[int] = Field(None, description="Document page number where risk occurs")


class DocumentRisksResponse(BaseModel):
    """
    Response schema for structured risk extraction.
    """
    document_id: str = Field(..., description="UUID of the analyzed document")
    risks: List[RiskItem] = Field(default_factory=list, description="List of structured risks identified")
    overall_risk_level: RiskSeverity = Field("MEDIUM", description="Aggregated risk assessment for the document")
    citations: List[Citation] = Field(default_factory=list, description="Verifiable citations for all risk findings")
    execution_route: List[str] = Field(default_factory=list, description="Graph path traversed")
    timing_ms: float = Field(0.0, description="Execution time in milliseconds")

