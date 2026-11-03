"""
Workflow orchestration service.

Why: Implementing an explicit service layer decouples HTTP transport semantics
from LangGraph state machine execution, error handling, timing metrics, and schema transformation.
"""

import time
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.schemas.workflow import (
    WorkflowRequest,
    WorkflowResponse,
    DocumentSummarizeRequest,
    DocumentSummarizeResponse,
    RiskItem,
    DocumentRisksResponse,
)
from app.workflows.graph import get_workflow_graph
from app.workflows.state import WorkflowState
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager

logger = logging.getLogger("nexusai.services.workflow")


class WorkflowService:
    """
    Coordinates LangGraph workflow execution for Q&A, summarization, and risk analysis.
    """

    @classmethod
    def run_workflow(cls, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute the unified LangGraph workflow with query routing.
        """
        t0 = time.perf_counter()
        logger.info(
            "Invoking LangGraph workflow: query='%s', doc_id=%s, type=%s",
            request.query,
            request.document_id,
            request.workflow_type,
        )

        initial_state: WorkflowState = {
            "query": request.query.strip(),
            "document_id": request.document_id,
            "requested_workflow_type": request.workflow_type,
            "top_k": request.top_k,
            "focus": None,
            "execution_route": [],
        }

        try:
            graph = get_workflow_graph()
            final_state: WorkflowState = graph.invoke(initial_state)
        except Exception as e:
            logger.error("LangGraph execution failure: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Workflow execution failed: {str(e)}"
            )

        timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return WorkflowResponse(
            workflow_type=final_state.get("workflow_type", "qa"),
            query=request.query,
            document_id=request.document_id,
            result=final_state.get("final_result", ""),
            structured_data=final_state.get("structured_data"),
            citations=final_state.get("citations") or [],
            insufficient_evidence=bool(final_state.get("insufficient_evidence", False)),
            execution_route=final_state.get("execution_route") or [],
            timing_ms=timing_ms,
        )

    @classmethod
    def summarize_document(
        cls,
        document_id: str,
        request: DocumentSummarizeRequest
    ) -> DocumentSummarizeResponse:
        """
        Execute document summarization branch via LangGraph.
        """
        t0 = time.perf_counter()
        logger.info("Summarizing document_id=%s (focus=%s)", document_id, request.focus)

        # Check document existence in indices
        vector_store = get_vector_store()
        doc_chunks = vector_store.get_chunks_by_document(document_id=document_id)
        if not doc_chunks:
            bm25 = get_bm25_manager()
            bm25_chunks = bm25.get_chunks_by_document(document_id=document_id)
            if not bm25_chunks:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document '{document_id}' not found in index."
                )

        initial_state: WorkflowState = {
            "query": f"Summarize document {document_id}",
            "document_id": document_id,
            "requested_workflow_type": "summarize",
            "top_k": 20,
            "focus": request.focus,
            "execution_route": [],
        }

        graph = get_workflow_graph()
        final_state: WorkflowState = graph.invoke(initial_state)
        timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        structured = final_state.get("structured_data") or {}

        return DocumentSummarizeResponse(
            document_id=document_id,
            summary=final_state.get("final_result", ""),
            executive_summary=structured.get("executive_summary"),
            key_findings=structured.get("key_findings") or [],
            action_items=structured.get("action_items") or [],
            citations=final_state.get("citations") or [],
            execution_route=final_state.get("execution_route") or [],
            timing_ms=timing_ms,
        )

    @classmethod
    def extract_document_risks(cls, document_id: str) -> DocumentRisksResponse:
        """
        Execute structured risk extraction branch via LangGraph.
        """
        t0 = time.perf_counter()
        logger.info("Extracting risks for document_id=%s", document_id)

        # Check document existence in indices
        vector_store = get_vector_store()
        doc_chunks = vector_store.get_chunks_by_document(document_id=document_id)
        if not doc_chunks:
            bm25 = get_bm25_manager()
            bm25_chunks = bm25.get_chunks_by_document(document_id=document_id)
            if not bm25_chunks:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document '{document_id}' not found in index."
                )

        initial_state: WorkflowState = {
            "query": f"Extract risks for document {document_id}",
            "document_id": document_id,
            "requested_workflow_type": "extract_risks",
            "top_k": 20,
            "focus": None,
            "execution_route": [],
        }

        graph = get_workflow_graph()
        final_state: WorkflowState = graph.invoke(initial_state)
        timing_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        structured = final_state.get("structured_data") or {}
        raw_risks = structured.get("risks") or []

        risk_items: List[RiskItem] = []
        for r in raw_risks:
            if not isinstance(r, dict):
                continue
            try:
                # Normalize keys to lowercase snake_case
                norm = {k.lower().replace(" ", "_").replace("-", "_"): v for k, v in r.items()}
                if "risk_id" not in norm and "id" in norm:
                    norm["risk_id"] = norm["id"]
                if "source_chunk_id" not in norm:
                    for alias in ["chunk_id", "source_chunk", "source", "source_id"]:
                        if alias in norm:
                            norm["source_chunk_id"] = str(norm[alias])
                            break
                    if "source_chunk_id" not in norm:
                        norm["source_chunk_id"] = f"{document_id}_p1_c0"
                if "severity" in norm and isinstance(norm["severity"], str):
                    norm["severity"] = norm["severity"].upper()
                if "mitigation" not in norm:
                    norm["mitigation"] = "Review policy controls and establish formal monitoring."
                risk_items.append(RiskItem(**norm))
            except Exception as e:
                logger.warning("Error mapping risk item: %s (raw: %s)", e, r)

        return DocumentRisksResponse(
            document_id=document_id,
            risks=risk_items,
            overall_risk_level=structured.get("overall_risk_level", "MEDIUM"),
            citations=final_state.get("citations") or [],
            execution_route=final_state.get("execution_route") or [],
            timing_ms=timing_ms,
        )

