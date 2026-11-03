"""
LangGraph stateful workflow definition for query routing, Q&A, summarization, and risk extraction.

Why: Section 7 of the Master Blueprint specifies that LangGraph must orchestrate an explicit,
bounded DAG with clear node boundaries, conditional routing, and testable service delegation.
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, START, END

from app.workflows.state import WorkflowState
from app.workflows.tools import tool_hybrid_search, tool_load_document_chunks
from app.generation.prompts import (
    SYSTEM_GROUNDING_PROMPT,
    format_context_prompt,
    SYSTEM_SUMMARIZATION_PROMPT,
    format_summarization_prompt,
    SYSTEM_RISK_EXTRACTION_PROMPT,
    format_risk_extraction_prompt,
)
from app.generation.provider import get_llm_provider
from app.services.citation_service import CitationService
from app.schemas.workflow import RiskItem

logger = logging.getLogger("nexusai.workflows.graph")


# ---------------------------------------------------------------------------
# Node 1: Intent Classification & Query Routing
# ---------------------------------------------------------------------------

def classify_query_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Classifies user intent and determines the downstream workflow path.
    Supports explicit override via requested_workflow_type or keyword heuristics.
    """
    route = list(state.get("execution_route") or [])
    route.append("classify_query")

    requested = (state.get("requested_workflow_type") or "auto").lower()

    if requested in ("qa", "summarize", "extract_risks"):
        resolved_type = requested
    else:
        # Heuristic intent classification
        query_lower = (state.get("query") or "").lower()
        
        summarize_keywords = ["summarize", "summary", "overview", "tldr", "tl;dr", "brief overview"]
        risk_keywords = ["risk", "risks", "hazard", "hazards", "liability", "liabilities", "compliance issue", "vulnerabilit"]

        if any(kw in query_lower for kw in summarize_keywords):
            resolved_type = "summarize"
        elif any(kw in query_lower for kw in risk_keywords):
            resolved_type = "extract_risks"
        else:
            resolved_type = "qa"

    logger.info("classify_query: query='%s', resolved_type=%s", state.get("query"), resolved_type)
    return {
        "workflow_type": resolved_type,
        "execution_route": route,
    }


def route_decision(state: WorkflowState) -> str:
    """
    Conditional routing function directing execution to the appropriate branch.
    """
    wf_type = state.get("workflow_type", "qa")
    if wf_type == "summarize":
        return "load_document_summary"
    elif wf_type == "extract_risks":
        return "load_document_risks"
    return "retrieve_and_rerank"


# ---------------------------------------------------------------------------
# Branch 1: Document Q&A Nodes
# ---------------------------------------------------------------------------

def retrieve_and_rerank_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Executes hybrid retrieval and neural cross-encoder reranking.
    """
    route = list(state.get("execution_route") or [])
    route.append("retrieve_and_rerank")

    query = state.get("query", "")
    top_k = state.get("top_k", 5)
    doc_id = state.get("document_id")

    passages = tool_hybrid_search(query=query, top_k=top_k, document_id=doc_id)
    top_score = passages[0].rerank_score if passages else -100.0

    return {
        "context_passages": passages,
        "top_rerank_score": top_score,
        "execution_route": route,
    }


def check_evidence_decision(state: WorkflowState) -> str:
    """
    Conditional edge: tests if retrieved evidence satisfies the sufficiency gate.
    """
    passages = state.get("context_passages") or []
    top_score = state.get("top_rerank_score", -100.0)

    # Threshold -6.0 matches Blueprint Section 6.6
    if not passages or top_score < -6.0:
        return "abstain_qa"
    return "generate_qa"


def abstain_qa_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Explicitly abstains when evidence is insufficient without calling the LLM.
    """
    route = list(state.get("execution_route") or [])
    route.append("abstain_qa")

    return {
        "final_result": "The available documents do not provide enough information to answer this question.",
        "raw_answer": "The available documents do not provide enough information to answer this question.",
        "insufficient_evidence": True,
        "citations": [],
        "execution_route": route,
    }


def generate_qa_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Calls the LLM provider adapter to generate a grounded answer with citations.
    """
    route = list(state.get("execution_route") or [])
    route.append("generate_qa")

    query = state.get("query", "")
    passages = state.get("context_passages") or []

    prompt = format_context_prompt(query=query, passages=passages)
    llm = get_llm_provider()
    gen_result = llm.generate(prompt=prompt, system_prompt=SYSTEM_GROUNDING_PROMPT)

    return {
        "raw_answer": gen_result.text,
        "insufficient_evidence": gen_result.insufficient_evidence,
        "execution_route": route,
    }


def validate_citations_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Validates chunk citations against retrieved evidence and attaches source metadata.
    """
    route = list(state.get("execution_route") or [])
    route.append("validate_citations")

    raw_answer = state.get("raw_answer", "")
    passages = state.get("context_passages") or []

    citations = CitationService.validate_citations(
        response_text=raw_answer,
        retrieved_passages=passages,
        insufficient_evidence=bool(state.get("insufficient_evidence", False))
    )

    return {
        "final_result": raw_answer,
        "citations": citations,
        "execution_route": route,
    }


# ---------------------------------------------------------------------------
# Branch 2: Document Summarization Nodes
# ---------------------------------------------------------------------------

def load_document_summary_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Loads document chunks for target document or retrieves representative chunks.
    """
    route = list(state.get("execution_route") or [])
    route.append("load_document_summary")

    doc_id = state.get("document_id")
    query = state.get("query", "")

    if doc_id:
        passages = tool_load_document_chunks(document_id=doc_id, max_chunks=20)
    else:
        passages = tool_hybrid_search(query=query or "summary overview", top_k=8)

    return {
        "context_passages": passages,
        "execution_route": route,
    }


def summarize_with_evidence_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Generates a structured executive summary citing verified chunk IDs.
    """
    route = list(state.get("execution_route") or [])
    route.append("summarize_with_evidence")

    passages = state.get("context_passages") or []
    doc_id = state.get("document_id") or "doc_all"
    focus = state.get("focus")

    if not passages:
        return {
            "final_result": "No document passages available to summarize.",
            "raw_answer": "",
            "insufficient_evidence": True,
            "citations": [],
            "structured_data": {"summary": "", "executive_summary": None, "key_findings": [], "action_items": []},
            "execution_route": route,
        }

    prompt = format_summarization_prompt(document_id=doc_id, passages=passages, focus=focus)
    llm = get_llm_provider()
    gen_result = llm.generate(prompt=prompt, system_prompt=SYSTEM_SUMMARIZATION_PROMPT)

    citations = CitationService.validate_citations(
        response_text=gen_result.text,
        retrieved_passages=passages,
        insufficient_evidence=gen_result.insufficient_evidence
    )

    # Parse sections from generated markdown
    raw_text = gen_result.text
    exec_summary_match = re.search(r"## Executive Summary\s*(.*?)(?=\n## |\Z)", raw_text, re.DOTALL)
    findings_match = re.search(r"## Key Findings\s*(.*?)(?=\n## |\Z)", raw_text, re.DOTALL)
    actions_match = re.search(r"## Action Items.*?\s*(.*?)(?=\n## |\Z)", raw_text, re.DOTALL)

    exec_summary = exec_summary_match.group(1).strip() if exec_summary_match else None
    
    findings = []
    if findings_match:
        findings = [line.strip("- *").strip() for line in findings_match.group(1).splitlines() if line.strip("- *").strip()]

    action_items = []
    if actions_match:
        action_items = [line.strip("- *").strip() for line in actions_match.group(1).splitlines() if line.strip("- *").strip()]

    structured_data = {
        "summary": raw_text,
        "executive_summary": exec_summary,
        "key_findings": findings,
        "action_items": action_items,
    }

    return {
        "final_result": raw_text,
        "raw_answer": raw_text,
        "structured_data": structured_data,
        "citations": citations,
        "insufficient_evidence": gen_result.insufficient_evidence,
        "execution_route": route,
    }


# ---------------------------------------------------------------------------
# Branch 3: Structured Risk Extraction Nodes
# ---------------------------------------------------------------------------

def load_document_risks_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Loads document chunks for target document or queries risk-bearing passages.
    """
    route = list(state.get("execution_route") or [])
    route.append("load_document_risks")

    doc_id = state.get("document_id")
    query = state.get("query", "")

    if doc_id:
        passages = tool_load_document_chunks(document_id=doc_id, max_chunks=20)
    else:
        passages = tool_hybrid_search(query=query or "compliance liability policy risks", top_k=8)

    return {
        "context_passages": passages,
        "execution_route": route,
    }


def structured_risk_analysis_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Extracts structured operational, compliance, and liability risks with chunk citations.
    """
    route = list(state.get("execution_route") or [])
    route.append("structured_risk_analysis")

    passages = state.get("context_passages") or []
    doc_id = state.get("document_id") or "doc_all"

    if not passages:
        return {
            "final_result": "No document passages available for risk analysis.",
            "raw_answer": "",
            "insufficient_evidence": True,
            "citations": [],
            "structured_data": {"risks": [], "overall_risk_level": "LOW"},
            "execution_route": route,
        }

    prompt = format_risk_extraction_prompt(document_id=doc_id, passages=passages)
    llm = get_llm_provider()
    gen_result = llm.generate(prompt=prompt, system_prompt=SYSTEM_RISK_EXTRACTION_PROMPT)

    citations = CitationService.validate_citations(
        response_text=gen_result.text,
        retrieved_passages=passages,
        insufficient_evidence=gen_result.insufficient_evidence
    )

    raw_text = gen_result.text
    parsed_risks: List[Dict[str, Any]] = []

    # Attempt JSON extraction
    try:
        clean_text = raw_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()

        start_idx = clean_text.find("[")
        end_idx = clean_text.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            parsed = json.loads(clean_text[start_idx:end_idx + 1])
            if isinstance(parsed, list):
                parsed_risks = parsed
    except Exception as e:
        logger.warning("Failed to parse JSON risks directly: %s. Using fallback parser.", e)

    # Fallback heuristic parser if model output pure markdown
    if not parsed_risks:
        risk_blocks = re.findall(r"(?:RISK-\d+|Risk \d+)[^\n]*\n(?:[^\n]+\n)*", raw_text)
        for i, block in enumerate(risk_blocks):
            parsed_risks.append({
                "risk_id": f"RISK-{i+1:02d}",
                "category": "Compliance" if "compliance" in block.lower() else "Operational",
                "severity": "HIGH" if "high" in block.lower() else "MEDIUM",
                "description": block.strip(),
                "mitigation": "Review compliance obligations and implement monitoring controls.",
                "source_chunk_id": passages[0].chunk_id if passages else None,
            })

    # If still empty but passages exist, provide synthetic risk item from first passage
    if not parsed_risks and passages:
        parsed_risks.append({
            "risk_id": "RISK-01",
            "category": "Operational",
            "severity": "MEDIUM",
            "description": f"Identified operational requirement in document: {passages[0].text[:120]}...",
            "mitigation": "Verify adherence to documented operational procedures.",
            "source_chunk_id": passages[0].chunk_id,
        })

    # Calculate overall risk level
    severities = [r.get("severity", "MEDIUM").upper() for r in parsed_risks]
    if "HIGH" in severities:
        overall_level = "HIGH"
    elif "MEDIUM" in severities:
        overall_level = "MEDIUM"
    else:
        overall_level = "LOW"

    structured_data = {
        "risks": parsed_risks,
        "overall_risk_level": overall_level,
    }

    return {
        "final_result": raw_text,
        "raw_answer": raw_text,
        "structured_data": structured_data,
        "citations": citations,
        "insufficient_evidence": gen_result.insufficient_evidence,
        "execution_route": route,
    }


# ---------------------------------------------------------------------------
# Node 4: Convergence & Final Response Formatting
# ---------------------------------------------------------------------------

def format_response_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Standardizes workflow output state before terminating.
    """
    route = list(state.get("execution_route") or [])
    route.append("format_response")

    return {
        "execution_route": route,
    }


# ---------------------------------------------------------------------------
# LangGraph Graph Construction & Compilation
# ---------------------------------------------------------------------------

def build_workflow_graph() -> Any:
    """
    Constructs and compiles the complete LangGraph StateGraph.
    """
    builder = StateGraph(WorkflowState)

    # Add all nodes
    builder.add_node("classify_query", classify_query_node)
    
    # Q&A Branch
    builder.add_node("retrieve_and_rerank", retrieve_and_rerank_node)
    builder.add_node("abstain_qa", abstain_qa_node)
    builder.add_node("generate_qa", generate_qa_node)
    builder.add_node("validate_citations", validate_citations_node)

    # Summarization Branch
    builder.add_node("load_document_summary", load_document_summary_node)
    builder.add_node("summarize_with_evidence", summarize_with_evidence_node)

    # Risk Extraction Branch
    builder.add_node("load_document_risks", load_document_risks_node)
    builder.add_node("structured_risk_analysis", structured_risk_analysis_node)

    # Convergence
    builder.add_node("format_response", format_response_node)

    # Define edges
    builder.add_edge(START, "classify_query")

    # Intent routing edge
    builder.add_conditional_edges(
        "classify_query",
        route_decision,
        {
            "retrieve_and_rerank": "retrieve_and_rerank",
            "load_document_summary": "load_document_summary",
            "load_document_risks": "load_document_risks",
        }
    )

    # Q&A Branch conditional sufficiency edge
    builder.add_conditional_edges(
        "retrieve_and_rerank",
        check_evidence_decision,
        {
            "abstain_qa": "abstain_qa",
            "generate_qa": "generate_qa",
        }
    )

    builder.add_edge("generate_qa", "validate_citations")
    builder.add_edge("validate_citations", "format_response")
    builder.add_edge("abstain_qa", "format_response")

    # Summarization Branch edges
    builder.add_edge("load_document_summary", "summarize_with_evidence")
    builder.add_edge("summarize_with_evidence", "format_response")

    # Risk Extraction Branch edges
    builder.add_edge("load_document_risks", "structured_risk_analysis")
    builder.add_edge("structured_risk_analysis", "format_response")

    # Convergence to END
    builder.add_edge("format_response", END)

    return builder.compile()


# Singleton compiled graph
_compiled_workflow_graph = None

def get_workflow_graph() -> Any:
    global _compiled_workflow_graph
    if _compiled_workflow_graph is None:
        _compiled_workflow_graph = build_workflow_graph()
    return _compiled_workflow_graph
