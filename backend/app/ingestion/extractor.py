"""
Format-specific text extraction modules for PDF, DOCX, and TXT documents.

Why: Isolating format parsers behind a common extraction interface guarantees that
format-specific library quirks (pypdf exceptions, docx xml structures) do not leak
into domain services or API routes. It also ensures consistent metadata generation
(page_number, character_count, whitespace normalization) across diverse file formats.
"""

import io
import re
from typing import List, Tuple
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from app.core.errors import CorruptedFileError
from app.schemas.document import PageExtraction


def normalize_extracted_text(raw_text: str) -> str:
    """
    Clean extracted text by removing control characters, excess empty lines, and redundant whitespace.
    
    Why: Document parsers frequently produce inconsistent whitespace, trailing form feeds,
    and carriage returns that degrade subsequent tokenization, chunking, and embedding quality.
    """
    if not raw_text:
        return ""
    # Replace non-breaking spaces and form feeds with standard whitespace
    text = raw_text.replace("\xa0", " ").replace("\x0c", "\n")
    # Collapse multiple consecutive horizontal spaces into one
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse more than two consecutive newlines into two
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(content_bytes: bytes) -> Tuple[List[PageExtraction], List[str]]:
    """
    Extract text page-by-page from PDF documents using pypdf.
    
    Why: Preserving page-level indexing (1-based) is crucial for grounded RAG citations,
    allowing users to verify claims against the exact page in the original PDF source.
    """
    pages: List[PageExtraction] = []
    warnings: List[str] = []

    try:
        reader = PdfReader(io.BytesIO(content_bytes))
        total_pages = len(reader.pages)
        if total_pages == 0:
            warnings.append("PDF contains zero pages.")
            return pages, warnings

        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_raw = page.extract_text() or ""
            except Exception:
                # Individual page extract failure should not abort the entire document
                page_raw = ""
                warnings.append(f"Failed to extract text from page {page_idx}.")

            clean_text = normalize_extracted_text(page_raw)
            pages.append(
                PageExtraction(
                    page_number=page_idx,
                    text=clean_text,
                    character_count=len(clean_text)
                )
            )

    except (PdfReadError, Exception) as exc:
        raise CorruptedFileError("Uploaded PDF file is corrupted or cannot be parsed.") from exc

    total_chars = sum(p.character_count for p in pages)
    if total_chars < 10:
        warnings.append(
            "Document contains no readable text or is near-empty. It may contain scanned images requiring OCR."
        )

    return pages, warnings


def extract_text_from_docx(content_bytes: bytes) -> Tuple[List[PageExtraction], List[str]]:
    """
    Extract text from DOCX documents, grouping paragraphs into logical section blocks.
    
    Why: Word documents do not have inherent physical page boundaries. Grouping paragraphs
    into coherent blocks (e.g., 5 paragraphs per logical page) provides stable structural
    references for downstream chunking and citations.
    """
    pages: List[PageExtraction] = []
    warnings: List[str] = []

    try:
        doc = Document(io.BytesIO(content_bytes))
        # Extract text from paragraphs
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        
        # Also extract text from tables if present
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        if not paragraphs:
            warnings.append("Document contains no readable text or is empty.")
            pages.append(PageExtraction(page_number=1, text="", character_count=0))
            return pages, warnings

        # Group paragraphs into logical blocks (5 paragraphs per block)
        group_size = 5
        for group_idx, i in enumerate(range(0, len(paragraphs), group_size), start=1):
            group_text = "\n\n".join(paragraphs[i:i + group_size])
            clean_text = normalize_extracted_text(group_text)
            pages.append(
                PageExtraction(
                    page_number=group_idx,
                    text=clean_text,
                    character_count=len(clean_text)
                )
            )

    except (PackageNotFoundError, Exception) as exc:
        raise CorruptedFileError("Uploaded DOCX file is corrupted or cannot be parsed.") from exc

    total_chars = sum(p.character_count for p in pages)
    if total_chars < 10:
        warnings.append("Document contains near-empty textual content.")

    return pages, warnings


def extract_text_from_txt(content_bytes: bytes) -> Tuple[List[PageExtraction], List[str]]:
    """
    Extract text from plain text documents as a single unified page block.
    
    Why: Plain text files lack internal paging, so presenting the file as a single
    logical page (page_number=1) simplifies uniform downstream ingestion pipelines.
    """
    warnings: List[str] = []

    try:
        raw_text = content_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raise CorruptedFileError("Failed to decode text document using UTF-8.") from exc

    clean_text = normalize_extracted_text(raw_text)
    if len(clean_text) < 10:
        warnings.append("Document contains no readable text or is empty.")

    pages = [
        PageExtraction(
            page_number=1,
            text=clean_text,
            character_count=len(clean_text)
        )
    ]
    return pages, warnings


def extract_document_text(content_bytes: bytes, file_type: str) -> Tuple[List[PageExtraction], List[str]]:
    """
    Unified extraction router dispatching to format-specific extractors.
    
    Why: Central dispatcher provides a single, uniform signature for the service layer
    regardless of the underlying file format.
    """
    if file_type == "pdf":
        return extract_text_from_pdf(content_bytes)
    elif file_type == "docx":
        return extract_text_from_docx(content_bytes)
    elif file_type == "txt":
        return extract_text_from_txt(content_bytes)
    else:
        raise CorruptedFileError(f"Unsupported file type for extraction: {file_type}")

