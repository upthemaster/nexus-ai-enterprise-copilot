"""
Bounded, read-only tools for LangGraph workflow execution.

Why: Section 7 of the Master Blueprint specifies that tools must be strictly controlled.
The MVP allows only bounded retrieval, document loading, and chunk inspection.
No shell access, unrestricted filesystem writes, or external network calls are permitted.
"""

import logging
from typing import List, Optional
from app.schemas.chat import RerankedPassage
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager

logger = logging.getLogger("nexusai.workflows.tools")


def tool_hybrid_search(
    query: str,
    top_k: int = 5,
    document_id: Optional[str] = None
) -> List[RerankedPassage]:
    """
    Execute hybrid retrieval (BM25 + ChromaDB Dense) followed by Cross-Encoder reranking.
    Read-only retrieval tool.
    """
    logger.debug("tool_hybrid_search: query='%s', top_k=%d, doc_id=%s", query, top_k, document_id)
    candidates = HybridRetriever.retrieve(
        query=query,
        top_k=top_k * 2,  # retrieve surplus before reranking
        document_id=document_id
    )

    if not candidates:
        return []

    reranker = CrossEncoderReranker.get_instance()
    return reranker.rerank(
        query=query,
        candidates=candidates,
        top_k=top_k
    )


def tool_load_document_chunks(
    document_id: str,
    max_chunks: int = 25
) -> List[RerankedPassage]:
    """
    Load ordered chunks for a target document from the persistent index.
    Read-only document inspection tool.
    """
    logger.debug("tool_load_document_chunks: doc_id=%s, max_chunks=%d", document_id, max_chunks)
    vector_store = get_vector_store()
    raw_chunks = vector_store.get_chunks_by_document(document_id=document_id)

    # Fallback to BM25 index if ChromaDB returns empty (e.g. index sync or reload)
    if not raw_chunks:
        bm25_manager = get_bm25_manager()
        bm25_chunks = bm25_manager.get_chunks_by_document(document_id=document_id)
        if bm25_chunks:
            return [
                RerankedPassage(
                    chunk_id=c.chunk_id,
                    document_id=c.metadata.document_id,
                    filename=c.metadata.filename,
                    page_number=c.metadata.page_number,
                    chunk_index=c.metadata.chunk_index,
                    text=c.text,
                    rerank_score=1.0
                )
                for c in bm25_chunks[:max_chunks]
            ]
        return []

    return [
        RerankedPassage(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            filename=item.filename,
            page_number=item.page_number,
            chunk_index=item.chunk_index,
            text=item.text,
            rerank_score=1.0
        )
        for item in raw_chunks[:max_chunks]
    ]


def tool_inspect_chunk(chunk_id: str) -> Optional[RerankedPassage]:
    """
    Inspect a specific chunk by its chunk ID.
    Read-only inspection tool.
    """
    vector_store = get_vector_store()
    item = vector_store.get_chunk_by_id(chunk_id)
    if item:
        return RerankedPassage(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            filename=item.filename,
            page_number=item.page_number,
            chunk_index=item.chunk_index,
            text=item.text,
            rerank_score=1.0
        )

    bm25 = get_bm25_manager()
    bm25_chunk = bm25.get_chunk_by_id(chunk_id)
    if bm25_chunk:
        return RerankedPassage(
            chunk_id=bm25_chunk.chunk_id,
            document_id=bm25_chunk.metadata.document_id,
            filename=bm25_chunk.metadata.filename,
            page_number=bm25_chunk.metadata.page_number,
            chunk_index=bm25_chunk.metadata.chunk_index,
            text=bm25_chunk.text,
            rerank_score=1.0
        )

    return None
