"""
Integration tests for local embeddings, persistent ChromaDB, and vector similarity search.

Why: Verifies that dense embeddings are generated locally, persisted to ChromaDB,
retrievable via semantic search, and protected against duplicate indexing via content hashes.
"""

import pytest
import httpx
from pathlib import Path

from app.schemas.document import PageExtraction
from app.ingestion.chunker import chunk_extracted_pages
from app.retrieval.embeddings import get_embedding_service
from app.retrieval.vector_store import get_vector_store
from app.services.indexing_service import IndexingService
from tests.conftest import generate_minimal_valid_pdf


def test_embedding_generation_local():
    """
    Test that local SentenceTransformer model generates 384-dimensional normalized vectors.
    """
    embedding_service = get_embedding_service()
    texts = ["Enterprise data governance and encryption standards.", "User access auditing policies."]
    embeddings = embedding_service.embed_documents(texts)

    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384

    query_vec = embedding_service.embed_query("data security")
    assert len(query_vec) == 384


def test_chromadb_upsert_and_query():
    """
    Test upserting chunks into ChromaDB and retrieving them via semantic similarity.
    """
    vector_store = get_vector_store()
    initial_count = vector_store.count()

    pages = [
        PageExtraction(
            page_number=1,
            text="NexusAI Security Standard: All external remote sessions must use hardware MFA keys.",
            character_count=87
        ),
        PageExtraction(
            page_number=2,
            text="NexusAI Travel Protocol: Business meal reimbursements require itemized receipts.",
            character_count=84
        )
    ]

    doc_id = "doc-security-policy"
    filename = "security_standard.pdf"
    chunks = chunk_extracted_pages(doc_id, filename, pages, chunk_size=200, chunk_overlap=20)
    
    embedding_service = get_embedding_service()
    embeddings = embedding_service.embed_documents([c.text for c in chunks])
    upserted = vector_store.upsert_chunks(chunks, embeddings)
    assert upserted == len(chunks)
    assert vector_store.count() == initial_count + len(chunks)

    # Query for security / MFA key requirements
    query_emb = embedding_service.embed_query("hardware authentication tokens")
    results = vector_store.query_similar(query_embedding=query_emb, top_k=2)

    assert len(results) >= 1
    top_hit = results[0]
    assert "MFA keys" in top_hit.text
    assert top_hit.page_number == 1
    assert top_hit.filename == filename
    assert top_hit.score > 0.4


def test_idempotent_deduplication():
    """
    Test that re-indexing identical content is detected and skipped.
    """
    pages = [
        PageExtraction(
            page_number=1,
            text="Proprietary algorithm specification for high-throughput stream fusion.",
            character_count=73
        )
    ]
    doc_id = "doc-algo-1"
    filename = "algorithm.txt"

    # First index attempt
    count1, hash1, is_duplicate1 = IndexingService.index_document(doc_id, filename, pages)
    assert count1 >= 1
    assert is_duplicate1 is False

    # Second index attempt with identical content
    count2, hash2, is_duplicate2 = IndexingService.index_document("doc-algo-2", "copy_algorithm.txt", pages)
    assert count2 == count1
    assert hash2 == hash1
    assert is_duplicate2 is True


@pytest.mark.asyncio
async def test_end_to_end_upload_and_vector_search(async_client: httpx.AsyncClient):
    """
    Test Day 2 exit criterion: an uploaded document is chunked, indexed,
    and immediately searchable via the POST /api/v1/search/vector API endpoint.
    """
    # Step 1: Upload valid document
    pdf_bytes = generate_minimal_valid_pdf("NexusAI Enterprise Copilot Hybrid Retrieval Engine")
    files = {"file": ("hybrid_retrieval.pdf", pdf_bytes, "application/pdf")}
    
    upload_resp = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["status"] == "processed"
    assert upload_data["chunk_count"] >= 1
    assert len(upload_data["content_hash"]) == 64

    # Step 2: Query vector search endpoint
    search_payload = {
        "query": "hybrid retrieval engine",
        "top_k": 3
    }
    search_resp = await async_client.post("/api/v1/search/vector", json=search_payload)
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    
    assert search_data["total_results"] >= 1
    first_result = search_data["results"][0]
    assert first_result["filename"] == "hybrid_retrieval.pdf"
    assert first_result["page_number"] == 1
    assert first_result["score"] > 0.0
    assert "NexusAI" in first_result["text"]

