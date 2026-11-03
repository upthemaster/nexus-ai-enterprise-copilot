"""
Document orchestration service.

Why: Implementing an explicit service layer decouples HTTP transport semantics
(FastAPI request/response handling) from core business logic (validation,
sanitization, safe disk persistence, text extraction, and vector indexing).
This guarantees reusability and testability.
"""

import uuid
import logging
from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings
from app.ingestion.validator import (
    sanitize_and_validate_filename,
    read_and_validate_file_stream,
    validate_file_signature,
)
from app.ingestion.extractor import extract_document_text
from app.services.indexing_service import IndexingService
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentSummaryItem,
    DocumentListResponse,
)
from app.db.session import SessionLocal
from app.db.models import DocumentModel
from app.retrieval.vector_store import get_vector_store
from datetime import datetime
from typing import Optional, List

# Structured logger for ingestion events
logger = logging.getLogger("nexusai.ingestion")


class DocumentService:
    """
    Coordinates the full document ingestion and indexing pipeline:
    1. Filename sanitization & path-traversal prevention.
    2. Streaming size enforcement.
    3. Magic byte signature verification.
    4. Safe persistent storage with UUID naming.
    5. Text and structural metadata extraction.
    6. Recursive chunking, local embedding, and persistent ChromaDB upserting.
    """

    @staticmethod
    async def process_document_upload(file: UploadFile) -> DocumentUploadResponse:
        """
        Execute full document ingestion and indexing workflow.
        
        Why: Centralizes the exact processing order required by Section 6.1 and 6.3 of the blueprint:
        Upload -> validate extension/mime/size -> assign document_id & safe filename ->
        extract text -> normalize -> detect empty -> chunk -> embed -> index into ChromaDB.
        """
        # Step 1: Validate and sanitize client-provided filename
        clean_filename, extension = sanitize_and_validate_filename(file.filename or "")

        # Step 2: Read bytes in chunks with stream-based size enforcement
        content_bytes = await read_and_validate_file_stream(
            file=file,
            max_size_bytes=settings.max_file_size_bytes
        )

        # Step 3: Validate binary magic header against claimed format
        validate_file_signature(
            header_bytes=content_bytes[:512],
            extension=extension
        )

        # Step 4: Assign internal UUID and generate safe server-side storage filename
        document_id = str(uuid.uuid4())
        safe_stored_filename = f"{document_id}.{extension}"
        storage_destination = settings.upload_path / safe_stored_filename

        try:
            with open(storage_destination, "wb") as f_out:
                f_out.write(content_bytes)
        except Exception as exc:
            logger.error("Failed to persist file to disk for document_id=%s", document_id)
            raise RuntimeError("Document storage failure.") from exc

        # Step 5: Extract text and structural metadata
        extracted_pages, warnings = extract_document_text(
            content_bytes=content_bytes,
            file_type=extension
        )

        total_characters = sum(page.character_count for page in extracted_pages)

        # Step 6: Chunk and index document into persistent vector store (Day 2)
        chunk_count, content_hash, is_duplicate = IndexingService.index_document(
            document_id=document_id,
            filename=clean_filename,
            pages=extracted_pages
        )

        if is_duplicate:
            status = "already_indexed"
        elif warnings:
            status = "warning"
        else:
            status = "processed"

        # Record document metadata in relational storage (SQLite)
        try:
            with SessionLocal() as db:
                doc_record = DocumentModel(
                    id=document_id,
                    filename=clean_filename,
                    file_type=extension,
                    content_hash=content_hash,
                    status="indexed",
                    chunk_count=chunk_count,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.merge(doc_record)
                db.commit()
        except Exception as db_err:
            logger.warning("Could not persist document metadata to SQLite: %s", db_err)

        logger.info(
            "Document processed: id=%s, pages=%d, chars=%d, chunks=%d, status=%s, warnings=%d",
            document_id,
            len(extracted_pages),
            total_characters,
            chunk_count,
            status,
            len(warnings)
        )

        return DocumentUploadResponse(
            document_id=document_id,
            filename=clean_filename,
            file_type=extension,
            status=status,
            extracted_pages=extracted_pages,
            character_count=total_characters,
            chunk_count=chunk_count,
            content_hash=content_hash,
            warnings=warnings
        )

    @staticmethod
    def list_documents() -> DocumentListResponse:
        """
        List all indexed documents from SQLite, with ChromaDB metadata fallback.
        
        Why: Fulfills Blueprint Table 10 (GET /api/v1/documents).
        """
        doc_map = {}
        # 1. Query relational store
        try:
            with SessionLocal() as db:
                records = db.query(DocumentModel).order_by(DocumentModel.created_at.desc()).all()
                for r in records:
                    doc_map[r.id] = DocumentSummaryItem(
                        id=r.id,
                        filename=r.filename,
                        file_type=r.file_type,
                        content_hash=r.content_hash or "",
                        status=r.status,
                        chunk_count=r.chunk_count,
                        created_at=r.created_at.isoformat() if r.created_at else datetime.utcnow().isoformat(),
                        updated_at=r.updated_at.isoformat() if r.updated_at else datetime.utcnow().isoformat(),
                    )
        except Exception as e:
            logger.warning("Failed to query documents from SQLite: %s", e)

        # 2. Reconcile with ChromaDB for any chunks indexed outside relational records (e.g. eval corpus)
        try:
            vs = get_vector_store()
            if vs.count() > 0:
                results = vs._collection.get(include=["metadatas"])
                if results and "metadatas" in results and results["metadatas"]:
                    for m in results["metadatas"]:
                        if not m:
                            continue
                        doc_id = m.get("document_id")
                        fn = m.get("filename", "unknown")
                        if doc_id and doc_id not in doc_map:
                            ext = fn.split(".")[-1] if "." in fn else "txt"
                            now_iso = datetime.utcnow().isoformat()
                            doc_map[doc_id] = DocumentSummaryItem(
                                id=doc_id,
                                filename=fn,
                                file_type=ext,
                                content_hash="",
                                status="indexed",
                                chunk_count=1,
                                created_at=now_iso,
                                updated_at=now_iso
                            )
                        elif doc_id and doc_id in doc_map:
                            # Verify chunk count if 0
                            if doc_map[doc_id].chunk_count == 0:
                                doc_map[doc_id].chunk_count += 1
        except Exception as e:
            logger.warning("Failed to reconcile documents with ChromaDB: %s", e)

        items = list(doc_map.values())
        return DocumentListResponse(total=len(items), documents=items)

    @staticmethod
    def get_document_details(document_id: str) -> Optional[DocumentSummaryItem]:
        """
        Retrieve single document details by ID.
        """
        all_docs = DocumentService.list_documents()
        for doc in all_docs.documents:
            if doc.id == document_id:
                return doc
        return None

    @staticmethod
    def delete_document(document_id: str) -> bool:
        """
        Delete document record from SQLite and remove chunks from vector store.
        """
        deleted = False
        try:
            with SessionLocal() as db:
                record = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
                if record:
                    db.delete(record)
                    db.commit()
                    deleted = True
        except Exception as e:
            logger.warning("Error deleting document from SQLite: %s", e)

        try:
            vs = get_vector_store()
            vs._collection.delete(where={"document_id": document_id})
            deleted = True
        except Exception as e:
            logger.warning("Error deleting document chunks from ChromaDB: %s", e)

        return deleted
