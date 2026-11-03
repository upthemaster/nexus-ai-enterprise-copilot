"""
Unit and integration tests for sparse BM25 keyword search.

Why: Verifies that BM25 provides accurate exact-match retrieval for technical codes,
policy identifiers, numbers, and hyphenated terms that vector search might blur.
"""

import pytest
import httpx
from pathlib import Path

from app.schemas.chunk import DocumentChunk, ChunkMetadata
from app.retrieval.bm25_index import BM25IndexManager, tokenize_text
from tests.conftest import generate_minimal_valid_pdf


def test_bm25_tokenization_preserves_identifiers():
    """
    Test that tokenizer preserves hyphenated identifiers, acronyms, and numbers.
    """
    raw = "Under Policy POL-402 and ISO-27001, port 8080 is restricted!"
    tokens = tokenize_text(raw)

    assert "pol-402" in tokens
    assert "iso-27001" in tokens
    assert "8080" in tokens
    assert "restricted" in tokens


def test_bm25_exact_code_matching():
    """
    Test that BM25 retrieves exact technical policy codes with high precision.
    """
    manager = BM25IndexManager()

    chunks = [
        DocumentChunk(
            chunk_id="chk-pol-402",
            text="Policy POL-402 strictly mandates hardware security keys for all remote VPN sessions.",
            metadata=ChunkMetadata(
                document_id="doc-security",
                filename="security.pdf",
                page_number=1,
                chunk_index=0,
                content_hash="hash-sec-402"
            )
        ),
        DocumentChunk(
            chunk_id="chk-pol-108",
            text="Policy POL-108 governs business travel expense limits and hotel booking reimbursements.",
            metadata=ChunkMetadata(
                document_id="doc-travel",
                filename="travel.pdf",
                page_number=1,
                chunk_index=0,
                content_hash="hash-trav-108"
            )
        )
    ]

    added = manager.add_chunks(chunks)
    assert added == 2
    assert manager.count() == 2

    # Query specifically for POL-402
    results = manager.query("POL-402", top_k=2)
    assert len(results) >= 1
    assert results[0].chunk_id == "chk-pol-402"
    assert "POL-402" in results[0].text
    assert results[0].score > 0.0

    # Query specifically for POL-108
    results_travel = manager.query("POL-108", top_k=2)
    assert len(results_travel) >= 1
    assert results_travel[0].chunk_id == "chk-pol-108"
    assert "POL-108" in results_travel[0].text


def test_bm25_disk_persistence_and_reload(tmp_path: Path):
    """
    Test that BM25 index corpus survives reloads and disk persistence.
    """
    persist_file = str(tmp_path / "custom_bm25.json")
    mgr1 = BM25IndexManager(persist_path=persist_file)

    chunk = DocumentChunk(
        chunk_id="chk-persist-1",
        text="Unique enterprise term: ZX-9990 cryptographic token rotation algorithm.",
        metadata=ChunkMetadata(
            document_id="doc-p1",
            filename="crypto.txt",
            page_number=1,
            chunk_index=0,
            content_hash="hash-p1"
        )
    )
    mgr1.add_chunks([chunk])
    assert mgr1.count() == 1

    # Reload from disk in a fresh instance
    mgr2 = BM25IndexManager(persist_path=persist_file)
    assert mgr2.count() == 1
    hits = mgr2.query("ZX-9990", top_k=1)
    assert len(hits) == 1
    assert hits[0].chunk_id == "chk-persist-1"


@pytest.mark.asyncio
async def test_bm25_api_endpoint(async_client: httpx.AsyncClient):
    """
    Test POST /api/v1/search/bm25 HTTP endpoint.
    """
    # Upload document containing an exact code
    pdf_bytes = generate_minimal_valid_pdf("Emergency Incident Protocol CODE-RED-777 applies.")
    files = {"file": ("incident_protocol.pdf", pdf_bytes, "application/pdf")}
    
    upload_resp = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 200

    # Query via BM25 endpoint
    bm25_resp = await async_client.post(
        "/api/v1/search/bm25",
        json={"query": "CODE-RED-777", "top_k": 3}
    )
    assert bm25_resp.status_code == 200
    data = bm25_resp.json()
    assert data["total_results"] >= 1
    assert "CODE-RED-777" in data["results"][0]["text"]
    assert data["results"][0]["filename"] == "incident_protocol.pdf"

