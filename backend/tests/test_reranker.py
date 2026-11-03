"""
Automated tests for Cross-Encoder passage reranking (Day 4).

Why: Verifies that the cross-encoder correctly discriminates semantic relevance,
orders the top-scoring passage first, and respects passthrough fallbacks.
"""

import pytest
from app.retrieval.reranker import get_reranker, CrossEncoderReranker
from app.schemas.search import HybridSearchResultItem, RetrievalDebugInfo


@pytest.fixture
def sample_candidates():
    """
    Creates a set of candidate passages with varying relevance to a query about leave policy.
    """
    return [
        HybridSearchResultItem(
            chunk_id="chunk_cafeteria",
            document_id="doc_ops",
            filename="facilities.txt",
            page_number=1,
            chunk_index=0,
            text="The office cafeteria is open from 8:00 AM to 4:00 PM on weekdays.",
            rrf_score=0.032,
            debug=RetrievalDebugInfo(vector_rank=1, bm25_rank=3, rrf_score=0.032)
        ),
        HybridSearchResultItem(
            chunk_id="chunk_leave",
            document_id="doc_hr",
            filename="employee_handbook.pdf",
            page_number=4,
            chunk_index=2,
            text="Employees receive 20 days of paid annual vacation leave and 10 days of sick leave.",
            rrf_score=0.030,
            debug=RetrievalDebugInfo(vector_rank=3, bm25_rank=1, rrf_score=0.030)
        ),
        HybridSearchResultItem(
            chunk_id="chunk_db",
            document_id="doc_tech",
            filename="architecture.docx",
            page_number=12,
            chunk_index=8,
            text="PostgreSQL connection pooling is configured with PgBouncer to manage high throughput.",
            rrf_score=0.028,
            debug=RetrievalDebugInfo(vector_rank=2, bm25_rank=4, rrf_score=0.028)
        )
    ]


def test_cross_encoder_reranks_most_relevant_passage_to_top(sample_candidates):
    """
    Verifies that for 'how many vacation days do employees get', the leave policy chunk
    is promoted to rank 1 over cafeteria hours, even if cafeteria had a higher first-stage RRF score.
    """
    reranker = get_reranker()
    query = "how many vacation days do employees get"
    
    reranked = reranker.rerank(query=query, candidates=sample_candidates, top_k=3)
    
    assert len(reranked) == 3
    # Most relevant passage must be rank 1
    assert reranked[0].chunk_id == "chunk_leave"
    assert "20 days of paid annual vacation" in reranked[0].text
    # Logit score for relevant chunk must be strictly higher than irrelevant chunk
    assert reranked[0].rerank_score > reranked[-1].rerank_score
    # Verify metadata fields are preserved
    assert reranked[0].document_id == "doc_hr"
    assert reranked[0].page_number == 4


def test_cross_encoder_empty_candidates():
    """
    Verifies that reranking an empty candidate pool returns an empty list safely without crashing.
    """
    reranker = get_reranker()
    reranked = reranker.rerank(query="anything", candidates=[], top_k=3)
    assert reranked == []


def test_cross_encoder_fallback_passthrough(sample_candidates):
    """
    Verifies that when reranking is bypassed, original RRF candidate order is preserved.
    """
    passthrough = CrossEncoderReranker.fallback_passthrough(sample_candidates, top_k=2)
    assert len(passthrough) == 2
    assert passthrough[0].chunk_id == "chunk_cafeteria"
    assert passthrough[1].chunk_id == "chunk_leave"
    assert passthrough[0].rerank_score == sample_candidates[0].rrf_score

