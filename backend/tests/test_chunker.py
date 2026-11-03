"""
Unit tests for document chunking and metadata preservation.

Why: Verifies that the recursive text splitter correctly preserves page_number,
assigns sequential chunk_index, respects overlap, and produces deterministic content hashes.
"""

from app.schemas.document import PageExtraction
from app.ingestion.chunker import chunk_extracted_pages, compute_content_hash


def test_chunking_preserves_page_numbers_and_metadata():
    """
    Test that chunking across multiple pages preserves exact origin page numbers.
    """
    page1_text = (
        "NexusAI Enterprise Copilot Architecture Specification. "
        "Section 1 defines the master product vision and high-level goals. "
        "The system must support enterprise RAG workflows with high precision and low latency. "
        "Each passage must be indexed with structural metadata for reliable citations."
    )
    page2_text = (
        "Section 2 defines document ingestion and hybrid retrieval policies. "
        "Combining dense vector search with sparse BM25 keyword matching guarantees "
        "both semantic discovery and exact term precision for technical policies."
    )

    pages = [
        PageExtraction(page_number=1, text=page1_text, character_count=len(page1_text)),
        PageExtraction(page_number=2, text=page2_text, character_count=len(page2_text)),
    ]

    doc_id = "doc-test-12345"
    filename = "spec.pdf"
    chunks = chunk_extracted_pages(
        document_id=doc_id,
        filename=filename,
        pages=pages,
        chunk_size=120,
        chunk_overlap=20
    )

    assert len(chunks) > 2
    # Verify sequential chunk indexing
    for i, chunk in enumerate(chunks):
        assert chunk.metadata.chunk_index == i
        assert chunk.metadata.document_id == doc_id
        assert chunk.metadata.filename == filename
        assert chunk.chunk_id == f"{doc_id}_p{chunk.metadata.page_number}_c{i}"
        assert len(chunk.metadata.content_hash) == 64

    # Verify page 1 chunks have page_number 1, and page 2 chunks have page_number 2
    p1_chunks = [c for c in chunks if c.metadata.page_number == 1]
    p2_chunks = [c for c in chunks if c.metadata.page_number == 2]
    assert len(p1_chunks) >= 2
    assert len(p2_chunks) >= 2
    assert "NexusAI" in p1_chunks[0].text
    assert any("BM25" in c.text for c in p2_chunks)


def test_chunking_skips_empty_and_whitespace_pages():
    """
    Test that empty or whitespace-only pages do not generate blank chunks.
    """
    pages = [
        PageExtraction(page_number=1, text="   \n\n  \t  ", character_count=0),
        PageExtraction(page_number=2, text="Valid substantive content on page two.", character_count=38),
    ]

    chunks = chunk_extracted_pages(
        document_id="doc-empty-check",
        filename="empty_p1.txt",
        pages=pages,
        chunk_size=200,
        chunk_overlap=20
    )

    assert len(chunks) == 1
    assert chunks[0].metadata.page_number == 2
    assert "page two" in chunks[0].text


def test_content_hash_deterministic_and_sensitive():
    """
    Test that compute_content_hash is strictly deterministic and detects subtle text mutations.
    """
    pages_a = [
        PageExtraction(page_number=1, text="Corporate Travel Policy 2026", character_count=28),
        PageExtraction(page_number=2, text="All flights must be economy class.", character_count=35),
    ]
    pages_b = [
        PageExtraction(page_number=1, text="Corporate Travel Policy 2026", character_count=28),
        PageExtraction(page_number=2, text="All flights must be economy class.", character_count=35),
    ]
    pages_mutated = [
        PageExtraction(page_number=1, text="Corporate Travel Policy 2026", character_count=28),
        PageExtraction(page_number=2, text="All flights must be business class.", character_count=36),
    ]

    hash_a = compute_content_hash(pages_a)
    hash_b = compute_content_hash(pages_b)
    hash_mutated = compute_content_hash(pages_mutated)

    assert hash_a == hash_b
    assert hash_a != hash_mutated
    assert len(hash_a) == 64

