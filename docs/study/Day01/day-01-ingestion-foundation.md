# Study Module: Day 1 — Ingestion Foundation & Document Processing

> **Target Role:** GenAI Engineer / Enterprise Systems Developer  
> **Status:** All components referenced in this document are labeled either **`[IMPLEMENTED]`** (verified working code in repository) or **`[PLANNED]`** (future roadmap scope).

---

## Architecture Visualizations

### Master System Architecture
![Master System Architecture](../images/system-architecture.svg)

### Day 1 Document Ingestion Flow
![Day 1 Upload Flow](../images/day-01-upload-flow.svg)

### Backend Module Map
![Day 1 Module Map](../images/day-01-module-map.svg)

---

## 1. Big Picture: What This Module Does and Why the Project Needs It

Retrieval-Augmented Generation (RAG) systems fail or succeed based on the quality and integrity of their ingestion pipeline. If corrupt, malicious, unparseable, or empty documents enter the system, every downstream component—chunking, vector embedding, similarity retrieval, and LLM answer generation—fails in unpredictable ways. A model cannot provide grounded answers or faithful citations if the source text was truncated, corrupted, or injected with malicious input.

The Day 1 Ingestion Foundation acts as the **secure gatekeeper** for NexusAI:
- It receives document uploads (`.pdf`, `.docx`, `.txt`) over HTTP.
- It validates that files are authentic, non-empty, and strictly within size boundaries.
- It neutralizes security threats like path traversal directory escapes and disguised binary executables.
- It extracts normalized text while preserving page and paragraph metadata required for future citations.
- It provides early warning detections when documents contain no readable text (e.g., scanned PDFs).

---

## 2. Concepts and Technologies

Each concept below covers: What it is, why we need it, how it works internally, where it appears in our code, a worked example, and common mistakes.

### 2.1 File Validation
* **What it is:** The process of ensuring an incoming file meets format, size, and structure requirements before processing.
* **Why we need it:** Preventing malformed or unhandled files from causing runtime crashes, Denial-of-Service (DoS), or unhandled exceptions in deep parsers.
* **How it works internally:** Inspects filename extensions against an allowed set (`ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"]`), validates non-zero content, and checks content headers.
* **Where it appears:** `backend/app/ingestion/validator.py` in `sanitize_and_validate_filename()`.
* **Worked Example:**
  ```python
  parts = safe_name.rsplit(".", 1)
  extension = parts[1].lower()
  if extension not in ["pdf", "docx", "txt"]:
      raise UnsupportedFileTypeError(f"File extension '.{extension}' is not permitted.")
  ```
* **Common Mistakes:** Relying purely on client-supplied `Content-Type` headers or file extensions without verifying content, allowing disguised files through.

### 2.2 Magic Bytes (File Signatures)
* **What it is:** Leading fixed byte sequences at the very beginning of a file that identify its actual binary format, regardless of its filename extension.
* **Why we need it:** Attackers can rename malware (`payload.exe` $\rightarrow$ `financial_report.pdf`). Parsing an executable with a PDF parser can cause crashes or exploit parser buffer overflows.
* **How it works internally:** Reads the first 4 to 16 bytes. A PDF must start with `%PDF-` (`0x25 0x50 0x44 0x46 0x2D`). A DOCX (which is an OpenXML ZIP container) must start with `PK\x03\x04` (`0x50 0x4B 0x03 0x04`). Plain text must decode cleanly as UTF-8 without binary null bytes (`\x00`).
* **Where it appears:** `backend/app/ingestion/validator.py` in `validate_file_signature()`.
* **Worked Example:**
  ```python
  MAGIC_SIGNATURES = {
      "pdf": [b"%PDF-"],
      "docx": [b"PK\x03\x04"],
  }
  if not any(header_bytes.startswith(sig) for sig in MAGIC_SIGNATURES[extension]):
      raise InvalidFileSignatureError("File signature mismatch.")
  ```
* **Common Mistakes:** Only reading text files as strings without checking for null bytes, causing binary files to trigger Unicode decoding crashes.

### 2.3 Path Traversal
* **What it is:** An attack technique where malicious path components (`../`, `..\`, `/etc/passwd`) are included in filenames to escape the intended upload folder.
* **Why we need it:** If an untrusted filename is concatenated with a filesystem directory (`upload_dir + "/" + filename`), an attacker can overwrite system binaries, configuration files, or user data.
* **How it works internally:** Checks for traversal patterns (`..`, `/`, `\`), extracts only the basename using `Path(filename).name`, and stores the physical file under a server-generated UUID (`{document_id}.{extension}`).
* **Where it appears:** `backend/app/ingestion/validator.py` in `sanitize_and_validate_filename()`, and `backend/app/services/document_service.py`.
* **Worked Example:**
  ```python
  # Neutralize: "../../../../Windows/System32/evil.dll"
  if ".." in raw_filename or raw_filename.startswith(("/", "\\")):
      raise PathTraversalError("Invalid directory traversal sequence.")
  safe_stored_name = f"{uuid.uuid4()}.{extension}"
  ```
* **Common Mistakes:** Trusting `os.path.basename()` on Linux when receiving Windows-style backslash paths (`..\..\`), or failing to use server-generated internal UUIDs for disk storage.

### 2.4 Text Extraction
* **What it is:** Extracting clean textual characters and structural boundaries from binary document formats (PDF, DOCX, TXT).
* **Why we need it:** LLMs and vector embedding models operate on plain text. Accurate citations require knowing which specific page or paragraph contained each statement.
* **How it works internally:**
  - **PDF:** `pypdf.PdfReader` parses cross-reference tables and streams, returning text per physical page with 1-based indexing.
  - **DOCX:** `python-docx` parses XML paragraph elements (`<w:p>`) and tables (`<w:tbl>`), grouping them into 5-paragraph logical blocks.
  - **TXT:** Direct UTF-8 stream decoding into a single logical block (`page_number=1`).
* **Where it appears:** `backend/app/ingestion/extractor.py` in `extract_document_text()`, `extract_text_from_pdf()`, `extract_text_from_docx()`, `extract_text_from_txt()`.
* **Worked Example:**
  ```python
  reader = PdfReader(io.BytesIO(content_bytes))
  for page_idx, page in enumerate(reader.pages, start=1):
      text = page.extract_text() or ""
      pages.append(PageExtraction(page_number=page_idx, text=text, character_count=len(text)))
  ```
* **Common Mistakes:** Flattening all pages into a single unstructured string, permanently losing the page numbers needed for citations.

### 2.5 FastAPI
* **What it is:** A modern, high-performance Python web framework based on Starlette (ASGI) and Pydantic.
* **Why we need it:** Async-native request handling, automatic OpenAPI/Swagger documentation, dependency injection, and declarative data validation.
* **How it works internally:** Uses Python type hints to parse and validate incoming HTTP requests asynchronously using ASGI event loops.
* **Where it appears:** `backend/app/main.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/endpoints/`.
* **Worked Example:**
  ```python
  @router.post("/upload", response_model=DocumentUploadResponse)
  async def upload_document(file: UploadFile = File(...)):
      return await DocumentService.process_document_upload(file=file)
  ```
* **Common Mistakes:** Writing blocking synchronous file I/O operations directly in route functions without `async/await` or run-in-threadpool execution, blocking the ASGI event loop.

### 2.6 Pydantic
* **What it is:** Data validation and settings management library using Python type annotations.
* **Why we need it:** Ensures all incoming payloads and outgoing API responses strictly follow defined contracts, auto-generating schema definitions and preventing type coercion bugs.
* **How it works internally:** Parses Python dictionaries/objects against typed models, executing field-level validators and serializing data into clean JSON primitives.
* **Where it appears:** `backend/app/schemas/health.py`, `backend/app/schemas/document.py`, `backend/app/core/config.py`.
* **Worked Example:**
  ```python
  class PageExtraction(BaseModel):
      page_number: int = Field(description="1-based page index")
      text: str = Field(description="Extracted content")
      character_count: int
  ```
* **Common Mistakes:** Returning arbitrary raw Python dictionaries from endpoints without a Pydantic response model, causing unexpected schema drift and silent contract violations.

### 2.7 Multipart Upload
* **What it is:** An HTTP standard (`multipart/form-data`) for streaming binary files and form fields in HTTP POST requests using boundary markers.
* **Why we need it:** Allows sending large binary files alongside metadata without encoding them into bulky Base64 JSON payloads (which adds ~33% bandwidth overhead).
* **How it works internally:** The HTTP request body contains parts separated by boundary strings. FastAPI wraps this in an `UploadFile` object providing an asynchronous file-like stream interface.
* **Where it appears:** `backend/app/api/v1/endpoints/documents.py` and `backend/app/ingestion/validator.py`.
* **Worked Example:**
  ```python
  async def read_and_validate_file_stream(file: UploadFile, max_size_bytes: int) -> bytes:
      chunks = []
      total = 0
      while chunk := await file.read(64 * 1024):
          total += len(chunk)
          if total > max_size_bytes:
              raise FileTooLargeError(...)
          chunks.append(chunk)
      return b"".join(chunks)
  ```
* **Common Mistakes:** Calling `await file.read()` with no byte limit, loading entire multi-gigabyte files into server RAM and crashing the server process.

### 2.8 Pytest
* **What it is:** A mature testing framework for Python supporting fixtures, parameterized tests, and async execution via `pytest-asyncio`.
* **Why we need it:** Guarantees regression protection, enforces quality gates, and proves that edge cases (corrupt files, traversal attempts, oversized payloads) fail safely.
* **How it works internally:** Discovers test functions matching `test_*`, injects declared fixtures, runs async test coroutines, and aggregates assertion failures.
* **Where it appears:** `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/tests/test_upload.py`.
* **Worked Example:**
  ```python
  @pytest.mark.asyncio
  async def test_upload_corrupt_pdf_handled(async_client: httpx.AsyncClient):
      files = {"file": ("bad.pdf", b"%PDF-1.4\ncorrupt_data", "application/pdf")}
      resp = await async_client.post("/api/v1/documents/upload", files=files)
      assert resp.status_code == 422
  ```
* **Common Mistakes:** Using hardcoded local paths in tests instead of temporary isolated fixtures (`tmp_path`), causing tests to leave state debris or fail on other machines.

### 2.9 Layered Architecture
* **What it is:** Separation of code into distinct horizontal layers with unidirectional dependencies: **Route $\rightarrow$ Service $\rightarrow$ Ingestion (Validator/Extractor) $\rightarrow$ Storage**.
* **Why we need it:** Prevents coupling HTTP transport details with document processing logic. The extraction service can be reused by CLI scripts, background workers, or evaluation runners without touching web routes.
* **How it works internally:** Route handlers handle HTTP parameters; services orchestrate business steps; validators and extractors contain pure parsing logic.
* **Where it appears:** Flowing from `api/v1/endpoints/documents.py` to `services/document_service.py` to `ingestion/validator.py` and `ingestion/extractor.py`.
* **Worked Example:**
  - Route handler receives `UploadFile` and calls `DocumentService.process_document_upload(file)`.
  - Service coordinates validation, UUID creation, disk writing, and extraction.
* **Common Mistakes:** Writing file parsing or database queries directly inside FastAPI route handlers (fat controllers).

### 2.10 Environment-Based Configuration
* **What it is:** Managing runtime configuration via environment variables and `.env` files rather than hardcoded literals.
* **Why we need it:** Adheres to the Twelve-Factor App methodology. Allows identical code to run in development, testing, staging, and production with different paths, limits, and keys.
* **How it works internally:** `pydantic-settings` reads system environment variables, attempts to load `.env`, validates types, and sets defaults.
* **Where it appears:** `backend/app/core/config.py` and `.env.example`.
* **Worked Example:**
  ```python
  class Settings(BaseSettings):
      MAX_FILE_SIZE_MB: int = 10
      ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt"]
      UPLOAD_DIR: str = "./data/uploads"
  ```
* **Common Mistakes:** Committing real secrets into `.env.example` or calling `os.getenv()` randomly across deep utility functions.

---

## 3. Alternatives Considered and Why Not Chosen

| Design Choice | Chosen Solution | Alternative Considered | Why Alternative Was Rejected |
| :--- | :--- | :--- | :--- |
| **PDF Extraction Library** | `pypdf` (5.3.0) | `pdfminer.six` / `PyMuPDF` (fitz) | `PyMuPDF` requires C-extensions and AGPL/commercial dual licensing. `pdfminer` is significantly slower on large documents. `pypdf` is pure-Python, BSD-licensed, lightweight, and supports reliable page-by-page extraction. |
| **DOCX Extraction Library** | `python-docx` (1.1.2) | Unzipping XML manually / `pandoc` | Unzipping raw XML is fragile and reinvents paragraph/table traversal. `pandoc` requires external system binary dependencies not universally available. |
| **File Size Enforcement** | Chunked stream read (64 KB) | Checking `request.headers["content-length"]` | The client-sent `Content-Length` header can be forged or omitted (e.g., chunked transfer encoding). Streaming enforces hard limits on actual bytes received. |
| **Storage Naming** | Internal UUID (`<uuid>.<ext>`) | Storing original sanitized filename | Filename collisions occur when multiple users upload `report.pdf`. UUID naming guarantees collision-free storage and completely eliminates path traversal exploits. |
| **Configuration Engine** | `pydantic-settings` | `os.environ` / `python-decouple` | `pydantic-settings` provides strict type parsing, validation at boot time, and seamless integration with FastAPI. |

---

## 4. Code Walkthrough in Data-Flow Order

### Step 1: Endpoint Receives Upload
*File:* `backend/app/api/v1/endpoints/documents.py`
```python
@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="Multipart file upload (PDF, DOCX, or TXT)")
) -> DocumentUploadResponse:
    # Route handler does not contain business logic; it immediately delegates to the service layer.
    return await DocumentService.process_document_upload(file=file)
```
*Why:* Maintains thin routes and decouples HTTP parameters from extraction logic.

### Step 2: Service Orchestrates Pipeline
*File:* `backend/app/services/document_service.py`
```python
clean_filename, extension = sanitize_and_validate_filename(file.filename or "")

content_bytes = await read_and_validate_file_stream(
    file=file,
    max_size_bytes=settings.max_file_size_bytes
)

validate_file_signature(
    header_bytes=content_bytes[:512],
    extension=extension
)
```
*Why:* Enforces strict order of operations: sanitize filename $\rightarrow$ stream bytes with memory bounds $\rightarrow$ verify binary signature before invoking any format parser.

### Step 3: Safe Disk Persistence
*File:* `backend/app/services/document_service.py`
```python
document_id = str(uuid.uuid4())
safe_stored_filename = f"{document_id}.{extension}"
storage_destination = settings.upload_path / safe_stored_filename

with open(storage_destination, "wb") as f_out:
    f_out.write(content_bytes)
```
*Why:* Filesystem writes use only the internal UUID and verified extension. The user-supplied filename is never used as a path component.

### Step 4: Text Extraction by Format
*File:* `backend/app/ingestion/extractor.py`
```python
def extract_text_from_pdf(content_bytes: bytes) -> Tuple[List[PageExtraction], List[str]]:
    try:
        reader = PdfReader(io.BytesIO(content_bytes))
        for page_idx, page in enumerate(reader.pages, start=1):
            page_raw = page.extract_text() or ""
            clean_text = normalize_extracted_text(page_raw)
            pages.append(PageExtraction(page_number=page_idx, text=clean_text, character_count=len(clean_text)))
    except (PdfReadError, Exception) as exc:
        raise CorruptedFileError("Uploaded PDF file is corrupted or cannot be parsed.") from exc
```
*Why:* Translates third-party parser exceptions into domain `CorruptedFileError`, preserving page boundaries for citations and normalizing whitespace.

### Step 5: Global Exception Sanitization
*File:* `backend/app/main.py`
```python
@application.exception_handler(NexusBaseException)
async def handle_nexus_domain_exception(request: Request, exc: NexusBaseException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "error_type": exc.error_type}
    )
```
*Why:* Ensures that internal tracebacks, Python module names, and server paths are never returned to clients.

---

## 5. Real Request / Response Trace (From Test Execution)

### Trace: Valid PDF Document Ingestion
**Request:**
```http
POST /api/v1/documents/upload HTTP/1.1
Host: test
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="enterprise_report.pdf"
Content-Type: application/pdf

%PDF-1.4
... [binary PDF stream: "NexusAI Production Evaluation Document Page 1"] ...
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**Actual Response (HTTP 200 OK):**
```json
{
  "document_id": "8c4e09f5-75e1-4c6e-827e-8559998ea3eb",
  "filename": "enterprise_report.pdf",
  "file_type": "pdf",
  "status": "processed",
  "extracted_pages": [
    {
      "page_number": 1,
      "text": "NexusAI Production Evaluation Document Page 1",
      "character_count": 46
    }
  ],
  "character_count": 46,
  "warnings": []
}
```

### Trace: Rejected Attack Attempt (Path Traversal)
**Request:**
```http
POST /api/v1/documents/upload HTTP/1.1
Host: test
Content-Disposition: form-data; name="file"; filename="../../../../etc/passwd.txt"
```

**Actual Response (HTTP 400 Bad Request):**
```json
{
  "error": "Filename contains invalid directory traversal sequences.",
  "error_type": "PathTraversalDetected"
}
```

---

## 6. Security and Edge Cases Handled

| Check / Guardrail | Threat / Failure Prevented | Implementation Mechanism |
| :--- | :--- | :--- |
| **Path Traversal Check** | Directory escape / arbitrary file overwrite. | Explicit rejection of `..`, `/`, `\`, null bytes; extraction of basename only; server-side UUID file naming. |
| **Streaming Size Limit** | Memory exhaustion / DoS via huge files. | Reads in 64 KB chunks, raising `FileTooLargeError` (HTTP 413) the instant `MAX_FILE_SIZE_MB` is exceeded. |
| **Magic Byte Signature** | Disguised executable upload / parser exploit. | Reads leading header bytes (`%PDF-`, `PK\x03\x04`, valid UTF-8 without nulls) before invoking format parsers. |
| **Corrupt File Handler** | Process crash / unhandled internal exceptions. | Traps `PdfReadError` and package format failures, converting them into sanitized HTTP 422 responses. |
| **Empty File Check** | Zero-byte processing errors / index corruption. | Validates `total_bytes > 0`, raising `EmptyDocumentError` (HTTP 400). |
| **Whitespace Normalizer** | Token waste / degraded embedding quality. | Replaces non-breaking spaces, form feeds, and redundant line breaks with clean normalized spacing. |
| **Safe Error Masking** | Information disclosure / stack trace leakage. | Global exception handlers sanitize all client-facing JSON responses; logs record safe event categories. |

---

## 7. Status & Scope Matrix: IMPLEMENTED vs PLANNED

| Component / Feature | Status | Location / Implementation Details |
| :--- | :--- | :--- |
| **GET /api/v1/health** | **`[IMPLEMENTED]`** | `backend/app/api/v1/endpoints/health.py` |
| **POST /api/v1/documents/upload** | **`[IMPLEMENTED]`** | `backend/app/api/v1/endpoints/documents.py` |
| **Pydantic Settings (`core/config.py`)** | **`[IMPLEMENTED]`** | `backend/app/core/config.py` |
| **Filename Sanitization & Traversal Check** | **`[IMPLEMENTED]`** | `backend/app/ingestion/validator.py` |
| **Magic Bytes Verification** | **`[IMPLEMENTED]`** | `backend/app/ingestion/validator.py` |
| **Streaming Size Enforcement (64 KB chunks)** | **`[IMPLEMENTED]`** | `backend/app/ingestion/validator.py` |
| **PDF Page-by-Page Text Extraction** | **`[IMPLEMENTED]`** | `backend/app/ingestion/extractor.py` (`pypdf`) |
| **DOCX Paragraph Block Text Extraction** | **`[IMPLEMENTED]`** | `backend/app/ingestion/extractor.py` (`python-docx`) |
| **TXT Single-Block Text Extraction** | **`[IMPLEMENTED]`** | `backend/app/ingestion/extractor.py` |
| **Empty / Near-Empty Extraction Warning** | **`[IMPLEMENTED]`** | `backend/app/ingestion/extractor.py` |
| **Safe Error Handlers (No Traces / Paths)** | **`[IMPLEMENTED]`** | `backend/app/main.py` |
| **Automated Test Suite (11 test cases)** | **`[IMPLEMENTED]`** | `backend/tests/test_upload.py`, `backend/tests/test_health.py` |
| **Text Chunking / Recursive Splitting** | **`[PLANNED]`** | Scheduled for Day 2 |
| **Sentence-Transformers Embeddings** | **`[PLANNED]`** | Scheduled for Day 2 |
| **Persistent ChromaDB Vector Store** | **`[PLANNED]`** | Scheduled for Day 2 |
| **BM25 Keyword Indexing** | **`[PLANNED]`** | Scheduled for Day 3 |
| **Hybrid Retrieval & Reciprocal Rank Fusion** | **`[PLANNED]`** | Scheduled for Day 3 |
| **Cross-Encoder Reranker** | **`[PLANNED]`** | Scheduled for Day 4 |
| **LLM Provider Adapter & Grounded Generation**| **`[PLANNED]`** | Scheduled for Day 4 |
| **Citation Verification & Insufficient Evidence**| **`[PLANNED]`** | Scheduled for Day 5 |
| **LangGraph Stateful Workflow Orchestration** | **`[PLANNED]`** | Scheduled for Day 6 |
| **Automated Evaluation Runner (RAGAS)** | **`[PLANNED]`** | Scheduled for Day 7 |
| **React UI Dashboard (Vite + Tailwind)** | **`[PLANNED]`** | Scheduled for Day 8 |
| **OCR for Scanned Document Bitmaps** | **`[PLANNED]`** | Deferred post-MVP hardening |

---

## 8. Interview Questions & Model Answers

### Category A: Basic Concepts
1. **Q: What is the risk of relying exclusively on file extensions to determine file type?**  
   *Answer:* File extensions are trivial for a client to alter. An attacker can rename an executable (`exploit.exe` to `exploit.pdf`). Relying solely on extensions can cause format parsers to crash or trigger binary execution vulnerabilities. Verifying magic bytes (e.g., `%PDF-`) ensures the binary content matches the claimed format before parsing.
2. **Q: Why does NexusAI assign a UUID to uploaded files rather than using the original filename on disk?**  
   *Answer:* Two reasons: first, to prevent filename collisions when multiple users upload files with identical names (e.g., `resume.docx`); second, to completely eliminate path traversal attacks (`../../`), ensuring the filesystem path is 100% server-controlled.
3. **Q: Why is page number metadata extracted and preserved during Day 1 ingestion?**  
   *Answer:* Grounded RAG requires traceable citations. Preserving page numbers at ingestion allows downstream chunks to carry original page metadata into the vector database, enabling the LLM response to cite exact pages for human verification.

### Category B: Intermediate Architecture
4. **Q: How does reading a file stream in 64 KB chunks protect the server against Denial of Service?**  
   *Answer:* Calling `await file.read()` reads the entire file into server RAM. A multi-gigabyte upload would trigger an Out-Of-Memory (OOM) crash. Streaming in 64 KB chunks tracks cumulative bytes read and aborts the connection with HTTP 413 the moment the limit is crossed, keeping memory usage constant.
5. **Q: Explain the role of the Service layer between the FastAPI route and the Ingestion extractor.**  
   *Answer:* The route handler deals strictly with HTTP mechanics (parsing multipart forms, status codes). The service coordinates domain business rules (validation, persistence, extraction, error aggregation). This allows the service to be invoked by test fixtures, background queues, or CLI tools without an active HTTP request.
6. **Q: What is the difference between an empty file error and a near-empty extraction warning?**  
   *Answer:* An empty file (0 bytes) is an invalid upload that cannot be processed (HTTP 400). A near-empty extraction occurs when a valid file (e.g., a scanned PDF with 2 megabytes of bitmap images) yields no extractable text characters. The upload succeeds (HTTP 200) but returns a warning advising that OCR is required.

### Category C: Advanced & System Design
7. **Q: Why should exception handlers never expose internal stack traces in an enterprise API?**  
   *Answer:* Stack traces reveal server paths, library versions, operating system details, and database schema structures to potential attackers. This information assists vulnerability exploitation. Production systems should log detailed traces internally with request IDs and return sanitized, categorical error messages to users.
8. **Q: How would you extend Day 1 extraction to handle scanned image-only PDFs without blocking the event loop?**  
   *Answer:* OCR engines (such as Tesseract or PaddleOCR) are CPU-bound and blocking. In FastAPI, CPU-bound extraction should be offloaded to a worker process or executed in a thread pool via `anyio.to_thread.run_sync()`, or offloaded to a background Celery/Redis queue for asynchronous processing.
9. **Q: Why did we choose pure-Python `pypdf` over C-based bindings like `PyMuPDF` for the Day 1 foundation?**  
   *Answer:* `pypdf` is pure-Python, BSD-licensed, and installs cleanly across Windows, Linux, and macOS without requiring C-compilers or external shared libraries (like Poppler). This guarantees zero platform installation friction while satisfying Day 1 page-level extraction needs.

### Category D: Scenario-Based
10. **Q: A user uploads a 9.9 MB PDF that expands to 400 MB of text in memory during parsing. How does the architecture respond?**  
    *Answer:* The streaming validator permits the upload because on-disk size is within the 10 MB limit. However, the text extractor streams pages individually and normalizes whitespace page-by-page. If memory limits are exceeded during parsing, the exception handler catches the crash and returns an HTTP 422 Unprocessable Entity error without bringing down the ASGI server.
11. **Q: A corporate proxy replaces original file headers with custom inspection headers. How do we prevent false rejections?**  
    *Answer:* Magic byte inspection checks the binary payload stream, not HTTP transport headers. Proxy header modifications do not alter the underlying file bytes (`%PDF-`), so inspection remains accurate and unaffected.
12. **Q: What happens if two identical documents are uploaded simultaneously by different users?**  
    *Answer:* Each upload receives a unique UUID `document_id` and independent storage filename, preventing write collisions. In Day 2, a SHA-256 `content_hash` check is planned to detect duplicates and prevent redundant vector embedding computation.

### Category E: Debugging & Troubleshooting
13. **Q: A test indicates that DOCX uploads fail with an `UnprocessableEntity` error. How do you diagnose the root cause?**  
    *Answer:* First, check if the file begins with `PK\x03\x04` magic bytes. If the signature is valid, verify if `python-docx` is encountering a corrupted XML schema or unsupported Word template feature. Inspect the server log for the trapped exception category without leaking raw file contents.
14. **Q: Why would a PDF upload return `status: "warning"` with zero extracted characters despite opening correctly in Adobe Acrobat?**  
    *Answer:* Adobe Acrobat displays rasterized page images and renders embedded fonts. The PDF is likely a scanned document containing bitmap images rather than selectable vector text streams. The Day 1 extractor correctly flags this with a warning suggesting OCR.
15. **Q: A tester reports that uploads of 11 MB files hang rather than immediately failing with HTTP 413. What is wrong?**  
    *Answer:* The endpoint might be reading the entire body before checking size, or an upstream reverse proxy (like NGINX) is buffering the full body before forwarding it to FastAPI. Ensuring chunked streaming reads inside `read_and_validate_file_stream()` fixes this at the application level.

### Category F: Trade-Off Analysis
16. **Q: What are the trade-offs of grouping DOCX paragraphs into 5-paragraph blocks rather than treating each paragraph as a page?**  
    *Answer:* Single paragraphs are often too short (1-2 sentences) to provide coherent semantic context for embeddings and LLM reasoning. Grouping paragraphs into 5-paragraph blocks preserves surrounding context while keeping chunks small enough for targeted retrieval citations.
17. **Q: Why enforce a strict extension whitelist instead of allowing any file and relying on MIME-type detection?**  
    *Answer:* MIME-type sniffers (such as `python-magic`) rely on heuristics that can be tricked or yield ambiguous types (`application/octet-stream`). A strict whitelist (`pdf`, `docx`, `txt`) enforces clear system boundaries and prevents users from uploading unsupported file types that the system cannot parse.
18. **Q: What is the trade-off between storing uploaded files on local disk versus directly passing bytes in memory to the chunker?**  
    *Answer:* Storing on local disk provides auditability, enables re-indexing without re-uploading, and decouples ingestion from asynchronous indexing. The trade-off is disk storage consumption, which requires cleanup and retention policies.

---

## 9. Self-Test & 60-Second Explanation Script

### Self-Test Questions
1. What are the specific magic byte headers for a PDF and a DOCX file?
2. Which HTTP status code is returned when a client attempts to upload an unsupported file extension like `.exe`?
3. What is the formula used in `core/config.py` to calculate `max_file_size_bytes`?
4. How does `sanitize_and_validate_filename` neutralize directory traversal characters?
5. Why are PDF pages extracted with 1-based indexing rather than 0-based indexing?
6. What happens when an uploaded document has less than 10 total extracted characters?
7. Where are the centralized exception handlers registered, and what do they prevent?
8. Why is `asyncio_mode = auto` configured in `pytest.ini`?

### 60-Second "Explain This Module" Script
> *"The Day 1 Ingestion Foundation for NexusAI is the secure entry point for our enterprise RAG pipeline. It exposes two core endpoints: a health check and a multipart document upload endpoint supporting PDFs, DOCX, and text files. 
> 
> Rather than blindly trusting incoming requests, the system implements defensive security: it streams files in 64-kilobyte buffers to abort oversized files before they consume memory; it checks binary magic byte signatures to block disguised executables; and it generates internal UUID filenames to eliminate path traversal vulnerabilities.
> 
> Validated documents are parsed page-by-page or block-by-block, preserving exact page numbers so that downstream LLM answers can provide verifiable citations. If a document is empty or scanned, the system surfaces clear warnings rather than failing silently. The entire module follows a clean Route-to-Service-to-Extractor architecture, fully covered by automated pytest suites with zero leaked stack traces."*

---

## 10. Module Glossary

* **ASGI (Asynchronous Server Gateway Interface):** Standard Python interface for asynchronous web servers (like Uvicorn) and applications (like FastAPI).
* **Chunked Streaming:** Reading an I/O data stream in small fixed-size memory blocks (e.g., 64 KB) to avoid loading massive payloads into memory all at once.
* **Corrupted File:** A file whose binary structure violates its specification and cannot be parsed by format readers.
* **Denial of Service (DoS):** An attack aimed at making a server or service unavailable to legitimate users, often by exhausting memory or CPU resources.
* **Magic Bytes:** Fixed binary sequences at the start of a file used to identify file type independently of its filename extension.
* **Multipart/Form-Data:** MIME format for submitting files and structured form fields in HTTP POST requests.
* **Near-Empty Document:** A document containing less than 10 extractable textual characters (e.g., image-only scans or blank templates).
* **Path Traversal:** A directory escape vulnerability using `../` patterns to access or overwrite unauthorized filesystem locations.
* **Pydantic Model:** A Python class inheriting from `BaseModel` that enforces type annotations and validates structured data at runtime.
* **Twelve-Factor App:** Best-practice methodology for building modern, scalable, cloud-ready applications with strict configuration separation.

