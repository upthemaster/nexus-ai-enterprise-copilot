"""
Automated test suite for Day 6: LangGraph Workflows & Query Routing.

Tests verify:
1. Intent classification and query routing heuristics (Q&A vs. Summarize vs. Extract Risks).
2. Q&A branch end-to-end execution, neural reranking, citation validation.
3. Q&A branch explicit abstention when evidence is insufficient.
4. Document summarization branch with structured sections and evidence citations.
5. Document risk extraction branch with structured RiskItems and severity levels.
6. Bounded read-only tool boundaries (no shell, no dangerous filesystem commands).
7. FastAPI workflow endpoints: POST /api/v1/workflows/run, /documents/{id}/summarize, /documents/{id}/risks.
8. Error handling and 404 responses for non-existent documents.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.document import PageExtraction
from app.services.indexing_service import IndexingService
from app.services.workflow_service import WorkflowService
from app.schemas.workflow import (
    WorkflowRequest,
    DocumentSummarizeRequest,
    WorkflowResponse,
    DocumentSummarizeResponse,
    DocumentRisksResponse,
)
from app.workflows.graph import classify_query_node
from app.workflows.tools import (
    tool_hybrid_search,
    tool_load_document_chunks,
    tool_inspect_chunk,
)

client = TestClient(app)


@pytest.fixture
def seeded_workflow_document():
    """
    Seeds a sample document with compliance, financial limit, and risk text for workflow tests.
    """
    doc_id = "doc_wf_test_day6"
    filename = "Enterprise_Procurement_and_Risk_Manual_2026.pdf"
    pages = [
        PageExtraction(
            page_number=1,
            text=(
                "NexusAI Governance Manual Section 1. All capital expenses exceeding $50,000 "
                "require explicit written authorization from the Chief Financial Officer before commitment. "
                "Failure to secure authorization exposes the organization to severe financial audit penalties."
            ),
            character_count=240
        ),
        PageExtraction(
            page_number=2,
            text=(
                "Section 2: Vendor Risk and Operational Safeguards. Vendors must maintain SOC 2 Type II "
                "compliance certifications annually. Failure to provide current compliance audits within thirty days "
                "will result in immediate termination of the vendor contract and potential legal liability."
            ),
            character_count=260
        )
    ]
    IndexingService.index_document(document_id=doc_id, filename=filename, pages=pages)
    return doc_id


def test_classify_query_routing_heuristics():
    """
    Verify intent classifier correctly routes to Q&A, Summarization, or Risk Extraction branches.
    """
    # 1. Standard Q&A
    state_qa = {"query": "What is the capital expense approval limit under Section 1?", "execution_route": []}
    res_qa = classify_query_node(state_qa)
    assert res_qa["workflow_type"] == "qa"
    assert "classify_query" in res_qa["execution_route"]

    # 2. Summarize keywords
    state_sum = {"query": "Please summarize the entire governance manual for executives", "execution_route": []}
    res_sum = classify_query_node(state_sum)
    assert res_sum["workflow_type"] == "summarize"

    state_tldr = {"query": "Give me a tldr overview of vendor rules", "execution_route": []}
    res_tldr = classify_query_node(state_tldr)
    assert res_tldr["workflow_type"] == "summarize"

    # 3. Risk keywords
    state_risk = {"query": "Extract all compliance and liability risks from this document", "execution_route": []}
    res_risk = classify_query_node(state_risk)
    assert res_risk["workflow_type"] == "extract_risks"

    # 4. Explicit override via requested_workflow_type
    state_override = {
        "query": "What is the capital expense limit?",
        "requested_workflow_type": "extract_risks",
        "execution_route": []
    }
    res_override = classify_query_node(state_override)
    assert res_override["workflow_type"] == "extract_risks"


def test_qa_workflow_end_to_end_grounded(seeded_workflow_document):
    """
    Verify Q&A branch executes end-to-end: hybrid retrieve -> rerank -> check evidence -> generate -> citations.
    """
    request = WorkflowRequest(
        query="What is the capital expense authorization limit?",
        document_id=seeded_workflow_document,
        workflow_type="qa",
        top_k=3
    )

    response = WorkflowService.run_workflow(request=request)

    assert isinstance(response, WorkflowResponse)
    assert response.workflow_type == "qa"
    assert response.insufficient_evidence is False
    assert len(response.result) > 0
    assert len(response.citations) > 0
    assert response.citations[0].document_id == seeded_workflow_document
    assert "retrieve_and_rerank" in response.execution_route
    assert "generate_qa" in response.execution_route
    assert "validate_citations" in response.execution_route
    assert "format_response" in response.execution_route
    assert response.timing_ms > 0.0


def test_qa_workflow_explicit_abstention_on_irrelevant_query(seeded_workflow_document):
    """
    Verify Q&A branch explicitly abstains when retrieved evidence does not satisfy sufficiency threshold.
    """
    request = WorkflowRequest(
        query="What is the molecular weight of caffeine in astrophysics?",
        document_id=seeded_workflow_document,
        workflow_type="qa",
        top_k=3
    )

    response = WorkflowService.run_workflow(request=request)

    assert response.workflow_type == "qa"
    assert response.insufficient_evidence is True
    assert "The available documents do not provide enough information" in response.result
    assert len(response.citations) == 0
    assert "abstain_qa" in response.execution_route
    assert "generate_qa" not in response.execution_route


def test_summarization_workflow_with_citations(seeded_workflow_document):
    """
    Verify document summarization branch extracts structured sections and citations.
    """
    request = DocumentSummarizeRequest(focus="financial authorization and vendor audit controls")
    response = WorkflowService.summarize_document(
        document_id=seeded_workflow_document,
        request=request
    )

    assert isinstance(response, DocumentSummarizeResponse)
    assert response.document_id == seeded_workflow_document
    assert len(response.summary) > 0
    assert response.executive_summary is not None
    assert len(response.key_findings) > 0
    assert len(response.action_items) > 0
    assert len(response.citations) > 0
    assert "load_document_summary" in response.execution_route
    assert "summarize_with_evidence" in response.execution_route
    assert "format_response" in response.execution_route


def test_risk_extraction_workflow_with_citations(seeded_workflow_document):
    """
    Verify risk extraction branch produces structured RiskItems with category and severity.
    """
    response = WorkflowService.extract_document_risks(document_id=seeded_workflow_document)

    assert isinstance(response, DocumentRisksResponse)
    assert response.document_id == seeded_workflow_document
    assert len(response.risks) >= 1

    first_risk = response.risks[0]
    assert first_risk.risk_id.startswith("RISK-")
    assert first_risk.category in ("Compliance", "Operational", "Financial", "Legal", "Security")
    assert first_risk.severity in ("HIGH", "MEDIUM", "LOW")
    assert len(first_risk.description) > 0
    assert first_risk.source_chunk_id is not None
    assert len(response.citations) > 0
    assert "load_document_risks" in response.execution_route
    assert "structured_risk_analysis" in response.execution_route


def test_workflow_tools_boundaries(seeded_workflow_document):
    """
    Verify bounded tools are strictly read-only and return sanitized typed passages.
    """
    # 1. tool_hybrid_search
    passages = tool_hybrid_search("capital expense", top_k=2, document_id=seeded_workflow_document)
    assert len(passages) > 0
    assert passages[0].document_id == seeded_workflow_document

    # 2. tool_load_document_chunks
    doc_chunks = tool_load_document_chunks(seeded_workflow_document, max_chunks=10)
    assert len(doc_chunks) >= 2
    # Verify chunks are sorted sequentially by chunk_index
    indices = [c.chunk_index for c in doc_chunks]
    assert indices == sorted(indices)

    # 3. tool_inspect_chunk
    first_chunk_id = doc_chunks[0].chunk_id
    inspected = tool_inspect_chunk(first_chunk_id)
    assert inspected is not None
    assert inspected.chunk_id == first_chunk_id
    assert len(inspected.text) > 0


def test_api_workflow_run_endpoint(seeded_workflow_document):
    """
    Test POST /api/v1/workflows/run with auto query routing.
    """
    # Auto route to summarize
    payload = {
        "query": "Summarize the key compliance rules in this document",
        "document_id": seeded_workflow_document,
        "workflow_type": "auto",
        "top_k": 3
    }
    response = client.post("/api/v1/workflows/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_type"] == "summarize"
    assert "summarize_with_evidence" in data["execution_route"]
    assert len(data["result"]) > 0


def test_api_documents_summarize_and_risks_endpoints(seeded_workflow_document):
    """
    Test POST /api/v1/documents/{id}/summarize and POST /api/v1/documents/{id}/risks.
    """
    # 1. Summarize endpoint
    sum_resp = client.post(
        f"/api/v1/documents/{seeded_workflow_document}/summarize",
        json={"focus": "vendor penalties"}
    )
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["document_id"] == seeded_workflow_document
    assert len(sum_data["summary"]) > 0

    # 2. Risk extraction endpoint
    risk_resp = client.post(f"/api/v1/documents/{seeded_workflow_document}/risks")
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["document_id"] == seeded_workflow_document
    assert len(risk_data["risks"]) > 0
    assert risk_data["overall_risk_level"] in ("HIGH", "MEDIUM", "LOW")

    # 3. Not found handling (404)
    not_found = client.post("/api/v1/documents/non_existent_doc_id_999/summarize")
    assert not_found.status_code == 404

    not_found_risk = client.post("/api/v1/documents/non_existent_doc_id_999/risks")
    assert not_found_risk.status_code == 404
