"""
Document ingestion endpoints.

Why: Thin HTTP routing layer that parses the multipart file upload and delegates
immediately to DocumentService. Keeping route handlers decoupled from extraction
and validation logic simplifies unit testing and preserves clean architectural boundaries.
"""

from typing import Optional, Dict
from fastapi import APIRouter, UploadFile, File, status, HTTPException
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentSummaryItem,
    DocumentListResponse,
)
from app.schemas.workflow import (
    DocumentSummarizeRequest,
    DocumentSummarizeResponse,
    DocumentRisksResponse,
)
from app.services.document_service import DocumentService
from app.services.workflow_service import WorkflowService
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and ingest a document",
    description=(
        "Validates file format, size, and magic bytes, stores file securely with a UUID, "
        "and extracts text content along with page/paragraph metadata."
    )
)
async def upload_document(
    file: UploadFile = File(..., description="Multipart file upload (PDF, DOCX, or TXT)")
) -> DocumentUploadResponse:
    """
    Handle document upload, validation, and extraction.
    """
    return await DocumentService.process_document_upload(file=file)


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all indexed documents",
    description="Returns metadata, chunk counts, and status for all ingested documents in the knowledge base."
)
def list_documents() -> DocumentListResponse:
    """
    List indexed documents.
    """
    return DocumentService.list_documents()


@router.get(
    "/{document_id}",
    response_model=DocumentSummaryItem,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Retrieve metadata and chunk counts for a specific document."
)
def get_document(document_id: str) -> DocumentSummaryItem:
    """
    Get single document details.
    """
    doc = DocumentService.get_document_details(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found."
        )
    return doc


@router.delete(
    "/{document_id}",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Delete a document",
    description="Removes document metadata and deletes corresponding vector chunks."
)
def delete_document(document_id: str) -> Dict[str, str]:
    """
    Delete document and associated chunks.
    """
    success = DocumentService.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found or could not be deleted."
        )
    return {"status": "deleted", "document_id": document_id}


@router.post(
    "/{document_id}/summarize",
    response_model=DocumentSummarizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Summarize an ingested document",
    description="Executes the LangGraph summarization branch on all chunks of the specified document."
)
def summarize_document(
    document_id: str,
    request: Optional[DocumentSummarizeRequest] = None
) -> DocumentSummarizeResponse:
    """
    Summarize a single document with evidence citations.
    """
    req = request or DocumentSummarizeRequest()
    return WorkflowService.summarize_document(document_id=document_id, request=req)


@router.post(
    "/{document_id}/risks",
    response_model=DocumentRisksResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured risks from an ingested document",
    description="Executes the LangGraph risk extraction branch, classifying operational, financial, and compliance risks."
)
def extract_risks(document_id: str) -> DocumentRisksResponse:
    """
    Extract structured risks with evidence citations from a single document.
    """
    return WorkflowService.extract_document_risks(document_id=document_id)

