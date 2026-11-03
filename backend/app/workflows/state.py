"""
Typed state schema for LangGraph workflows.

Why: LangGraph coordinates multi-node workflows by passing an immutable or mutated state
dictionary across graph edges. A strict TypedDict guarantees field availability and type safety.
"""

from typing import TypedDict, List, Optional, Dict, Any
from app.schemas.chat import RerankedPassage, Citation


class WorkflowState(TypedDict, total=False):
    """
    State object passed between LangGraph nodes during workflow execution.
    """
    # Inputs
    query: str
    document_id: Optional[str]
    requested_workflow_type: str
    top_k: int
    focus: Optional[str]

    # Intent Classification
    workflow_type: str  # "qa", "summarize", or "extract_risks"

    # Retrieval & Reranking Evidence
    context_passages: List[RerankedPassage]
    top_rerank_score: float

    # Generation & Evaluation
    raw_answer: str
    final_result: str
    structured_data: Optional[Dict[str, Any]]
    citations: List[Citation]
    insufficient_evidence: bool

    # Observability & Route Tracking
    execution_route: List[str]
    error: Optional[str]

