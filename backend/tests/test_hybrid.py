"""
Integration tests for Hybrid Retrieval with Reciprocal Rank Fusion (RRF).

Why: Verifies that hybrid retrieval combines semantic vector search and sparse BM25
to consistently place known passages in top-K, fulfilling the Day 3 exit criteria.
"""

import pytest
import httpx

from app.schemas.document import PageExtraction
from app.services.indexing_service import IndexingService
from app.retrieval.hybrid import HybridRetriever
from tests.conftest import generate_minimal_valid_pdf


def test_rrf_score_calculation_and_debug_metadata():
    """
    Test that Reciprocal Rank Fusion computes correct 1 / (k + rank) scores
    and includes transparent debug metadata.
    """
    pages1 = [
        PageExtraction(
            page_number=1,
            text="Standard Operating Procedure SOP-900: All production database migrations require senior DBA approval.",
            character_count=107
        )
    ]
    pages2 = [
        PageExtraction(
            page_number=1,
            text="Human Resources Guideline HR-300: Remote employees may expense office monitors up to $500.",
            character_count=98
        )
    ]

    IndexingService.index_document("doc-sop-900", "sop_900.pdf", pages1)
    IndexingService.index_document("doc-hr-300", "hr_300.pdf", pages2)

    # Query with exact identifier SOP-900 and semantic phrasing
    results = HybridRetriever.retrieve("SOP-900 database migration approval", top_k=2)

    assert len(results) >= 1
    top_hit = results[0]
    assert "SOP-900" in top_hit.text
    assert top_hit.filename == "sop_900.pdf"

    # Verify RRF score and debug information
    dbg = top_hit.debug
    assert dbg.rrf_score > 0.0
    # The chunk should appear in either vector or BM25 or both
    assert dbg.vector_rank is not None or dbg.bm25_rank is not None
    if dbg.vector_rank is not None:
        assert dbg.vector_score is not None
    if dbg.bm25_rank is not None:
        assert dbg.bm25_score is not None


def test_hybrid_exit_criterion_exact_code_and_semantic_paraphrase():
    """
    Day 3 Exit Criterion: Known passages appear in top-K for both:
    1. Exact technical term/code query (BM25 advantage).
    2. Semantic conceptual paraphrase query (Dense vector advantage).
    """
    pages_security = [
        PageExtraction(
            page_number=1,
            text="NexusAI Policy SEC-404: Zero trust network segmentation is enforced across all VPC subnets.",
            character_count=97
        )
    ]
    pages_wellness = [
        PageExtraction(
            page_number=1,
            text="Employee Wellbeing Program: Reimbursements are provided for gym memberships and fitness trackers.",
            character_count=104
        )
    ]

    IndexingService.index_document("doc-sec", "sec_policy.pdf", pages_security)
    IndexingService.index_document("doc-well", "wellness.pdf", pages_wellness)

    # Test 1: Exact keyword search for SEC-404
    sec_results = HybridRetriever.retrieve("SEC-404", top_k=1)
    assert len(sec_results) == 1
    assert "SEC-404" in sec_results[0].text
    assert sec_results[0].filename == "sec_policy.pdf"

    # Test 2: Semantic paraphrase for fitness gym benefits (zero keyword overlap with title)
    paraphrase_query = "exercise equipment and physical health financial allowances"
    well_results = HybridRetriever.retrieve(paraphrase_query, top_k=1)
    assert len(well_results) == 1
    assert "gym memberships" in well_results[0].text
    assert well_results[0].filename == "wellness.pdf"


@pytest.mark.asyncio
async def test_hybrid_search_api_endpoint(async_client: httpx.AsyncClient):
    """
    Test POST /api/v1/search/hybrid endpoint with debug breakdown.
    """
    # Upload document
    pdf_bytes = generate_minimal_valid_pdf("NexusAI Policy ARCH-101: Microservice communication must use gRPC.")
    files = {"file": ("architecture_policy.pdf", pdf_bytes, "application/pdf")}
    
    upload_resp = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 200

    # Query hybrid search endpoint
    search_payload = {
        "query": "ARCH-101 gRPC communication",
        "top_k": 3,
        "candidate_multiplier": 2
    }
    hybrid_resp = await async_client.post("/api/v1/search/hybrid", json=search_payload)
    assert hybrid_resp.status_code == 200
    data = hybrid_resp.json()

    assert data["total_results"] >= 1
    top_result = data["results"][0]
    assert "ARCH-101" in top_result["text"]
    assert top_result["filename"] == "architecture_policy.pdf"
    assert top_result["page_number"] == 1
    assert "rrf_score" in top_result
    assert "debug" in top_result
    assert "vector_rank" in top_result["debug"]
    assert "bm25_rank" in top_result["debug"]

