# NexusAI Enterprise Copilot — Technical Interview Q&A Bank

> This repository document serves as an exhaustive reference for technical interviews and architectural defense. Every answer reflects actual implementations and design decisions in NexusAI.

---

## 1. Basic Concepts

### Q1: What is the risk of relying exclusively on file extensions to determine file type?
**Answer:**  
File extensions are client-supplied metadata that can be trivially manipulated. An attacker can rename an executable (`malware.exe` to `annual_report.pdf`). If the backend relies solely on the extension, it forwards binary data to document parsers, potentially causing crashes or exploiting parser vulnerabilities. Verifying magic bytes (e.g., `%PDF-` for PDFs) ensures the binary structure matches the claimed type before parsing begins.

### Q2: Why does NexusAI assign an internal UUID to uploaded files instead of saving them under their original filenames?
**Answer:**  
Using original filenames creates two major risks: filename collisions when multiple users upload files with identical names (e.g., `invoice.pdf`), and path traversal attacks (`../../etc/passwd`) where malicious path fragments escape target directories. Storing files as `<uuid>.<extension>` guarantees collision-free storage and neutralizes filesystem navigation attacks.

### Q3: Why is page number metadata extracted and preserved during Day 1 document ingestion?
**Answer:**  
High-quality RAG requires verifiable, traceable citations. Preserving page numbers during initial ingestion ensures that downstream text chunks inherit their physical page locations. When the LLM generates an answer, it can point users to the exact source page, maintaining auditability and user trust.

---

## 2. Intermediate Architecture

### Q4: How does chunked streaming protect the backend against memory exhaustion (DoS)?
**Answer:**  
Standard file reads (`await file.read()`) load the entire file into server RAM. Uploading an oversized file (e.g., 2 GB) can trigger an Out-Of-Memory (OOM) crash that kills the server. Reading the incoming stream in 64 KB buffers tracks cumulative size and immediately halts with HTTP 413 (Payload Too Large) the instant the limit is crossed, bounding memory usage.

### Q5: Explain the role and necessity of the Service layer between the API router and Ingestion extractors.
**Answer:**  
The route handler should only concern itself with HTTP transport concerns: reading multipart forms, status codes, and JSON responses. The service layer coordinates business domain rules: filename sanitization, stream size verification, UUID assignment, disk persistence, and text extraction. This keeps routes lightweight and allows the service to be invoked by test runners, background workers, or CLI scripts without HTTP overhead.

### Q6: What distinguishes an empty file error from a near-empty extraction warning?
**Answer:**  
An empty file (0 bytes) is a client error that contains no data and is rejected immediately with HTTP 400. A near-empty extraction occurs when a valid file (e.g., a 5 MB scanned PDF of bitmap images) contains zero selectable text characters. The upload succeeds (HTTP 200) but includes a warning informing the caller that the file may require OCR.

---

## 3. Advanced & System Design

### Q7: Why must API exception handlers sanitize error responses and strip stack traces?
**Answer:**  
Raw stack traces reveal internal filesystem paths, operating system configurations, database schemas, and third-party library versions. This information lowers the barrier for attackers searching for known CVEs. Enterprise APIs must log complete traces internally with request correlation IDs and return only sanitized, categorical error descriptions to clients.

### Q8: How would you extend Day 1 extraction to handle scanned image-only PDFs without blocking the ASGI event loop?
**Answer:**  
OCR engines (like Tesseract) perform intensive, CPU-bound image processing. Executing OCR synchronously within an async FastAPI handler blocks the ASGI event loop and stalls all concurrent user requests. To avoid this, CPU-bound parsing should be offloaded to a thread pool via `anyio.to_thread.run_sync()`, a background process pool via `ProcessPoolExecutor`, or a distributed queue (Celery/RabbitMQ).

### Q9: Why was pure-Python `pypdf` selected over C-based bindings like `PyMuPDF` for the Day 1 foundation?
**Answer:**  
`pypdf` is pure-Python, BSD-licensed, and installs cleanly across Windows, Linux, and macOS without requiring C-compilers or system-level shared libraries (like Poppler). This eliminates cross-platform build friction during initial setup while providing reliable page-by-page text extraction for RAG citations.

---

## 4. Scenario-Based Design

### Q10: A user uploads a 9.9 MB PDF that expands to 400 MB of text during extraction. How does the system handle this?
**Answer:**  
The streaming validator permits the upload because the compressed on-disk size is within the 10 MB limit. However, the text extractor streams pages individually and normalizes whitespace page-by-page. If memory limits are exceeded during parsing, the exception handler catches the crash and returns an HTTP 422 Unprocessable Entity error without bringing down the ASGI server.

### Q11: An enterprise proxy strips or alters client HTTP Content-Type headers. How does NexusAI prevent false upload rejections?
**Answer:**  
NexusAI does not rely on client-supplied `Content-Type` headers for security decisions. Instead, it inspects the actual binary stream headers (magic bytes: `%PDF-` for PDF, `PK\x03\x04` for DOCX). Modifications to transport headers by proxies do not alter the underlying binary payload, so inspection remains reliable.

### Q12: What happens if two identical documents are uploaded simultaneously by different users?
**Answer:**  
Each upload receives an independent UUID `document_id` and is stored under a distinct filename, preventing filesystem collisions. In Day 2, a SHA-256 `content_hash` check will be added to identify identical documents, enabling deduplication and avoiding redundant embedding computations.

---

## 5. Debugging & Troubleshooting

### Q13: A test reports that DOCX uploads fail with an `UnprocessableEntity` (HTTP 422) error. What steps do you take to isolate the cause?
**Answer:**  
First, check if the file begins with `PK\x03\x04` magic bytes. If the signature is valid, verify if `python-docx` is encountering a corrupted XML schema or unsupported Word template feature. Inspect the server log for the trapped exception category without leaking raw file contents.

### Q14: Why would a PDF upload return `status: "warning"` with zero extracted characters despite opening correctly in Adobe Acrobat?
**Answer:**  
Adobe Acrobat renders embedded font vectors and displays rasterized bitmap images. If the PDF was produced by a desktop scanner, it contains page pictures without underlying text streams. The Day 1 extractor correctly flags this condition with a warning indicating that OCR is needed.

### Q15: An upload of an 11 MB file hangs rather than immediately failing with HTTP 413. What is the root cause?
**Answer:**  
This occurs if the endpoint reads the entire request payload into memory before checking the size, or if an upstream reverse proxy (like NGINX) is buffering the request before forwarding it to FastAPI. Using chunked stream reads in `read_and_validate_file_stream()` fixes this at the application layer.

---

## 6. Trade-Off Analysis

### Q16: What are the trade-offs of grouping DOCX paragraphs into 5-paragraph blocks instead of treating each paragraph as a page?
**Answer:**  
Individual paragraphs are often too short (1-2 sentences) to retain complete semantic context for embeddings and LLM reasoning. Grouping paragraphs into 5-paragraph blocks provides sufficient contextual depth while maintaining fine-grained structural references for citations.

### Q17: Why enforce a strict extension whitelist rather than allowing arbitrary file uploads with MIME sniffing?
**Answer:**  
MIME sniffers rely on probabilistic heuristics that frequently classify unknown or arbitrary binary files as generic `application/octet-stream`. A strict whitelist (`pdf`, `docx`, `txt`) provides an explicit security boundary, ensuring the system only accepts formats for which verified parsers exist.

### Q18: What is the trade-off of persisting raw uploaded files to disk versus passing memory buffers directly to the indexer?
**Answer:**  
Persisting raw files ensures auditability, allows re-indexing when embedding models change without re-uploading, and decouples ingestion from asynchronous indexing. The trade-off is disk storage consumption, which requires ongoing cleanup and retention management.

