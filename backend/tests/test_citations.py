"""
Automated tests for citation verification, quote detection, and source inspection (Day 5).

Why: Verifies Section 6.6 and Table 8 requirements:
- Direct quotations vs. paraphrases are accurately distinguished.
- Fabricated citation IDs are strictly discarded.
- Source inspection endpoint returns full passage text and metadata.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.chat import RerankedPassage
from app.schemas.document import PageExtraction
from app.services.citation_service import CitationService
from app.services.indexing_service import IndexingService


@pytest.fixture
def sample_passages():
    return [
        RerankedPassage(
            chunk_id="chunk_sec_99",
            document_id="doc_sec",
            filename="security_handbook.pdf",
            page_number=3,
            chunk_index=0,
            text="All employees must rotate their passwords every ninety calendar days without exception.",
            rerank_score=4.5,
            original_hybrid_rank=1,
            rrf_score=0.032
        ),
        RerankedPassage(
            chunk_id="chunk_hr_55",
            document_id="doc_hr",
            filename="hr_guide.docx",
            page_number=1,
            chunk_index=0,
            text="Standard working hours are flexible between 8:00 AM and 6:00 PM Monday through Friday.",
            rerank_score=1.2,
            original_hybrid_rank=2,
            rrf_score=0.028
        )
    ]


def test_direct_quote_detection_true(sample_passages):
    """
    Verifies that verbatim text spans are flagged as direct quotations.
    """
    answer = (
        "According to the handbook, all employees must rotate their passwords every ninety calendar days "
        "to remain compliant [chunk_sec_99]."
    )
    valid_cites, panel_items, discarded = CitationService.validate_and_enrich(
        cited_chunk_ids=["chunk_sec_99"],
        retrieved_passages=sample_passages,
        generated_answer=answer
    )

    assert len(valid_cites) == 1
    assert valid_cites[0].is_direct_quote is True
    assert valid_cites[0].quote_span is not None
    assert "passwords every ninety calendar days" in valid_cites[0].quote_span.lower()
    assert panel_items[0].is_direct_quote is True


def test_direct_quote_detection_false_for_paraphrase(sample_passages):
    """
    Verifies that paraphrased answers without long verbatim spans have is_direct_quote=False.
    """
    answer = "Staff need to update their system access credentials on a quarterly cycle."
    valid_cites, panel_items, discarded = CitationService.validate_and_enrich(
        cited_chunk_ids=["chunk_sec_99"],
        retrieved_passages=sample_passages,
        generated_answer=answer
    )

    assert len(valid_cites) == 1
    assert valid_cites[0].is_direct_quote is False
    assert valid_cites[0].quote_span is None


def test_citation_validation_discards_hallucinated_ids(sample_passages):
    """
    Verifies that hallucinated chunk IDs are stripped from valid citations and reported.
    """
    cited = ["chunk_sec_99", "chunk_fabricated_9999", "chunk_fake_foo"]
    valid_cites, panel_items, discarded = CitationService.validate_and_enrich(
        cited_chunk_ids=cited,
        retrieved_passages=sample_passages,
        generated_answer="Policy states passwords rotate regularly."
    )

    assert len(valid_cites) == 1
    assert valid_cites[0].chunk_id == "chunk_sec_99"
    assert "chunk_fabricated_9999" in discarded
    assert "chunk_fake_foo" in discarded


@pytest.mark.asyncio
async def test_source_inspector_endpoint_success(tmp_path, monkeypatch):
    """
    Verifies GET /api/v1/citations/{chunk_id} returns full chunk text and metadata.
    """
    chroma_dir = tmp_path / "chroma_source_inspect"
    bm25_file = tmp_path / "bm25_source_inspect.json"
    sqlite_db = tmp_path / "nexusai_test.db"

    monkeypatch.setattr("app.core.config.settings.CHROMA_PERSIST_DIR", str(chroma_dir))
    monkeypatch.setattr("app.core.config.settings.BM25_PERSIST_PATH", str(bm25_file))
    monkeypatch.setattr("app.core.config.settings.SQLITE_DB_PATH", str(sqlite_db))

    text = "Detailed compliance regulation COMP-101 requires annual cybersecurity awareness training for all staff."
    IndexingService.index_document(
        document_id="doc_comp_101",
        filename="compliance_101.pdf",
        pages=[PageExtraction(page_number=2, text=text, character_count=len(text))]
    )

    target_chunk_id = "doc_comp_101_p2_c0"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/citations/{target_chunk_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_id"] == target_chunk_id
        assert data["document_id"] == "doc_comp_101"
        assert data["filename"] == "compliance_101.pdf"
        assert data["page_number"] == 2
        assert "COMP-101" in data["text"]
        assert data["character_count"] == len(text)


@pytest.mark.asyncio
async def test_source_inspector_endpoint_not_found():
    """
    Verifies GET /api/v1/citations/{chunk_id} returns HTTP 404 for non-existent IDs.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/citations/non_existent_chunk_12345")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

