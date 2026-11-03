"""
Structural, page-aware document chunking module.

Why: RAG systems require splitting large documents into smaller, semantically coherent
passages that fit within embedding and LLM context limits. Crucially, chunking must
preserve the origin page_number for every generated chunk so downstream citations
can accurately reference the exact source page in the original document.
"""

import hashlib
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.schemas.document import PageExtraction
from app.schemas.chunk import DocumentChunk, ChunkMetadata


def compute_content_hash(pages: List[PageExtraction]) -> str:
    """
    Compute a deterministic SHA-256 hash over the combined text of all extracted pages.
    
    Why: Generating a content hash enables idempotent ingestion: re-uploading an unchanged
    document can be detected immediately, preventing duplicate vectors and wasted embedding computation.
    """
    hasher = hashlib.sha256()
    for page in sorted(pages, key=lambda p: p.page_number):
        hasher.update(page.text.strip().encode("utf-8"))
    return hasher.hexdigest()


def chunk_extracted_pages(
    document_id: str,
    filename: str,
    pages: List[PageExtraction],
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP
) -> List[DocumentChunk]:
    """
    Split extracted pages into overlapping text chunks while strictly preserving page metadata.
    
    Why: By splitting within individual page boundaries, chunks are never arbitrarily
    split across physical pages without retaining their true origin page_number.
    """
    content_hash = compute_content_hash(pages)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
        length_function=len,
    )

    chunks: List[DocumentChunk] = []
    chunk_index = 0

    for page in pages:
        clean_page_text = page.text.strip()
        if not clean_page_text:
            continue

        raw_splits = splitter.split_text(clean_page_text)
        for split in raw_splits:
            clean_split = split.strip()
            if not clean_split:
                continue

            chunk_id = f"{document_id}_p{page.page_number}_c{chunk_index}"
            metadata = ChunkMetadata(
                document_id=document_id,
                filename=filename,
                page_number=page.page_number,
                chunk_index=chunk_index,
                content_hash=content_hash
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=clean_split,
                    metadata=metadata
                )
            )
            chunk_index += 1

    return chunks

