"""
Document file validation: extensions, path traversal, magic bytes, and stream size.

Why: Implementing rigorous multi-stage validation before handing raw files to
third-party format parsers mitigates Server-Side Request Forgery (SSRF), Denial of Service
via memory exhaustion (zip/file bombs), Remote Code Execution via parser exploits,
and Arbitrary File Overwrite via Path Traversal attacks.
"""

import re
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import (
    UnsupportedFileTypeError,
    FileTooLargeError,
    InvalidFileSignatureError,
    PathTraversalError,
    EmptyDocumentError,
)

# Known magic byte signatures for allowed document types
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "docx": [b"PK\x03\x04"],  # Standard OpenXML / ZIP archive header
}

# 64 KB buffer size for chunked streaming reads
CHUNK_SIZE_BYTES = 64 * 1024


def sanitize_and_validate_filename(raw_filename: str) -> Tuple[str, str]:
    r"""
    Validate and sanitize the upload filename, returning (clean_name, extension).
    
    Why: Attackers can supply filenames like `../../etc/passwd` or `..\Windows\System32\cmd.exe`
    to escape intended upload directories. We reject explicit traversal sequences and strip
    all leading path elements using Pathlib.
    """
    if not raw_filename or not raw_filename.strip():
        raise PathTraversalError("Filename cannot be empty or whitespace.")

    # Detect explicit path traversal sequences or null bytes
    if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename or "\x00" in raw_filename:
        # Check if caller tried relative or absolute directory navigation
        if ".." in raw_filename or raw_filename.startswith(("/", "\\")):
            raise PathTraversalError("Filename contains invalid directory traversal sequences.")

    # Strip any client-side path prefixes to extract only the final component
    safe_name = Path(raw_filename).name.strip()
    if not safe_name:
        raise PathTraversalError("Filename is invalid after sanitization.")

    # Extract extension
    parts = safe_name.rsplit(".", 1)
    if len(parts) < 2 or not parts[1]:
        raise UnsupportedFileTypeError("File must have a valid extension (.pdf, .docx, or .txt).")

    extension = parts[1].lower()
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"File extension '.{extension}' is not permitted. Allowed extensions: {settings.ALLOWED_EXTENSIONS}"
        )

    # Sanitize characters in filename to alphanumeric, dots, hyphens, and underscores
    sanitized_basename = re.sub(r"[^\w\.-]", "_", parts[0])
    cleaned_filename = f"{sanitized_basename}.{extension}"

    return cleaned_filename, extension


def validate_file_signature(header_bytes: bytes, extension: str) -> None:
    """
    Verify magic byte signatures against the claimed file extension.
    
    Why: File extensions are easily spoofed by renaming an executable or arbitrary binary.
    Verifying leading magic bytes ensures we do not pass binary executables to PDF/DOCX parsers.
    """
    if extension in MAGIC_SIGNATURES:
        expected_headers = MAGIC_SIGNATURES[extension]
        matched = any(header_bytes.startswith(sig) for sig in expected_headers)
        if not matched:
            raise InvalidFileSignatureError(
                f"File content does not match the expected binary signature for extension '.{extension}'."
            )
    elif extension == "txt":
        # Text files do not have a fixed magic header, but must not be binary executable or contain null bytes
        if b"\x00" in header_bytes[:512]:
            raise InvalidFileSignatureError(
                "Plain text document contains binary null bytes and cannot be processed as text."
            )
        try:
            # Check if initial chunk decodes cleanly as UTF-8 or ASCII
            header_bytes[:512].decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise InvalidFileSignatureError("Plain text document must be valid UTF-8 encoded text.")


async def read_and_validate_file_stream(file: UploadFile, max_size_bytes: int) -> bytes:
    """
    Read file asynchronously in chunks while strictly enforcing maximum size limits.
    
    Why: Reading a multi-gigabyte upload directly into memory via `await file.read()` causes
    server Out-Of-Memory (OOM) crashes. Streaming in 64KB increments allows us to abort immediately
    the moment the configured threshold is exceeded, keeping memory usage constant and bounded.
    """
    total_bytes = 0
    chunks = []

    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_size_bytes:
            max_mb = max_size_bytes // (1024 * 1024)
            raise FileTooLargeError(
                f"File size exceeds maximum permitted limit of {max_mb}MB."
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise EmptyDocumentError("Uploaded file is empty (0 bytes).")

    return b"".join(chunks)

