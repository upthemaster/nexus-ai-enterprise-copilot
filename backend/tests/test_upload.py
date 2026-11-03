"""
Ingestion test suite for document upload, validation, and extraction.

Why: Thoroughly exercises all positive and negative security/operational paths:
- Valid PDF, DOCX, TXT uploads.
- Unsupported file extension rejection (HTTP 415).
- Empty (0-byte) file rejection (HTTP 400).
- Corrupt file parsing failure handling (HTTP 422).
- Oversized file rejection during streaming (HTTP 413).
- Path traversal filename neutralization (HTTP 400).
- Disguised file signature spoofing rejection (HTTP 400).
- Near-empty document warning generation.
"""

import pytest
import httpx

from app.core.config import settings
from tests.conftest import generate_minimal_valid_pdf, generate_valid_docx


@pytest.mark.asyncio
async def test_upload_valid_pdf_success(async_client: httpx.AsyncClient):
    """
    Test uploading a standard valid PDF document.
    """
    pdf_bytes = generate_minimal_valid_pdf("NexusAI Production Evaluation Document Page 1")
    files = {"file": ("enterprise_report.pdf", pdf_bytes, "application/pdf")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "processed"
    assert data["file_type"] == "pdf"
    assert data["filename"] == "enterprise_report.pdf"
    assert "document_id" in data
    assert data["character_count"] > 0
    assert len(data["extracted_pages"]) == 1
    assert data["extracted_pages"][0]["page_number"] == 1
    assert "NexusAI" in data["extracted_pages"][0]["text"]
    assert len(data["warnings"]) == 0


@pytest.mark.asyncio
async def test_upload_valid_docx_success(async_client: httpx.AsyncClient):
    """
    Test uploading a standard valid DOCX document.
    """
    docx_bytes = generate_valid_docx("Quarterly Enterprise Risk Analysis Findings.")
    files = {
        "file": (
            "risk_report.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    }
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "processed"
    assert data["file_type"] == "docx"
    assert data["filename"] == "risk_report.docx"
    assert data["character_count"] > 0
    assert len(data["extracted_pages"]) >= 1
    assert data["extracted_pages"][0]["page_number"] == 1
    assert "Risk Analysis" in data["extracted_pages"][0]["text"]


@pytest.mark.asyncio
async def test_upload_valid_txt_success(async_client: httpx.AsyncClient):
    """
    Test uploading a standard valid TXT document.
    """
    txt_bytes = b"Policy 402: All remote access must require multi-factor authentication tokens."
    files = {"file": ("security_policy.txt", txt_bytes, "text/plain")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "processed"
    assert data["file_type"] == "txt"
    assert data["filename"] == "security_policy.txt"
    assert len(data["extracted_pages"]) == 1
    assert data["extracted_pages"][0]["page_number"] == 1
    assert data["character_count"] == len(txt_bytes.decode("utf-8").strip())
    assert "Policy 402" in data["extracted_pages"][0]["text"]


@pytest.mark.asyncio
async def test_upload_unsupported_extension_rejected(async_client: httpx.AsyncClient):
    """
    Test rejection of files with extensions outside the allowed whitelist.
    """
    files = {"file": ("malicious_payload.exe", b"MZ\x90\x00executable", "application/x-msdownload")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 415
    data = response.json()
    assert data["error_type"] == "UnsupportedMediaType"
    assert "File extension '.exe' is not permitted" in data["error"]


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(async_client: httpx.AsyncClient):
    """
    Test rejection of empty (0-byte) file uploads.
    """
    files = {"file": ("empty_notes.txt", b"", "text/plain")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_type"] == "EmptyDocument"
    assert "0 bytes" in data["error"]


@pytest.mark.asyncio
async def test_upload_corrupt_pdf_handled(async_client: httpx.AsyncClient):
    """
    Test handling of corrupted PDF files that fail parsing.
    """
    # Header starts with PDF magic bytes, but subsequent content is corrupted garbage
    corrupt_pdf_bytes = b"%PDF-1.4\nthis is completely corrupt and unparseable binary data stream"
    files = {"file": ("corrupt.pdf", corrupt_pdf_bytes, "application/pdf")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 422
    data = response.json()
    assert data["error_type"] == "UnprocessableEntity"
    assert "corrupted or cannot be parsed" in data["error"]


@pytest.mark.asyncio
async def test_upload_oversized_file_rejected(async_client: httpx.AsyncClient, monkeypatch):
    """
    Test rejection of files exceeding MAX_FILE_SIZE_MB during streaming.
    """
    # Temporarily set max file size to 1 MB for testing
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    
    # Create 1.5 MB payload
    oversized_bytes = b"A" * (int(1.5 * 1024 * 1024))
    files = {"file": ("oversized_archive.txt", oversized_bytes, "text/plain")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 413
    data = response.json()
    assert data["error_type"] == "PayloadTooLarge"
    assert "exceeds maximum permitted limit" in data["error"]


@pytest.mark.asyncio
async def test_upload_path_traversal_filename_neutralized(async_client: httpx.AsyncClient):
    """
    Test rejection of path-traversal directory escape attempts in filename.
    """
    txt_bytes = b"Sample safe content."
    files = {"file": ("../../../../etc/passwd.txt", txt_bytes, "text/plain")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_type"] == "PathTraversalDetected"
    assert "directory traversal" in data["error"]


@pytest.mark.asyncio
async def test_upload_fake_pdf_signature_rejected(async_client: httpx.AsyncClient):
    """
    Test rejection of executable/random bytes spoofed with a .pdf extension.
    """
    # Claimed as .pdf but lacking %PDF- magic bytes
    fake_pdf_bytes = b"NOT_A_REAL_PDF_HEADER_JUST_RANDOM_TEXT_BYTES"
    files = {"file": ("spoofed.pdf", fake_pdf_bytes, "application/pdf")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_type"] == "InvalidFileSignature"
    assert "does not match the expected binary signature" in data["error"]


@pytest.mark.asyncio
async def test_upload_near_empty_warning(async_client: httpx.AsyncClient):
    """
    Test warning generation when document text is near-empty (< 10 characters).
    """
    near_empty_txt = b"abc"
    files = {"file": ("scant.txt", near_empty_txt, "text/plain")}
    
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "warning"
    assert len(data["warnings"]) >= 1
    assert "near-empty" in data["warnings"][0] or "no readable text" in data["warnings"][0]


@pytest.mark.asyncio
async def test_list_and_get_documents_lifecycle(async_client: httpx.AsyncClient):
    """
    Test listing documents, fetching single document details, and deletion.
    """
    # 1. Upload a valid document
    txt_content = b"Enterprise Security Standard Section 4. Multi-factor authentication is mandatory."
    files = {"file": ("test_lifecycle_policy.txt", txt_content, "text/plain")}
    upload_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]

    # 2. List documents
    list_res = await async_client.get("/api/v1/documents")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    found = any(d["id"] == doc_id for d in list_data["documents"])
    assert found

    # 3. Get single document details
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == doc_id
    assert get_data["filename"] == "test_lifecycle_policy.txt"

    # 4. Delete document
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 5. Non-existent document 404
    not_found_res = await async_client.get(f"/api/v1/documents/non_existent_uuid_12345")
    assert not_found_res.status_code == 404


