# NexusAI Enterprise Copilot — Master Living Glossary

> This living glossary records all technical, architectural, and GenAI concepts introduced throughout the implementation of NexusAI. Terms are categorized and tagged with their live implementation status.

---

## Foundation & Document Ingestion Terms (Day 1)

### ASGI (Asynchronous Server Gateway Interface)
*Definition:* The standard Python specification for asynchronous web servers and applications (such as FastAPI and Uvicorn). Enables concurrent handling of high-volume network I/O without blocking worker threads.  
*Status:* **`[IMPLEMENTED]`** — Powers the FastAPI backend in `backend/app/main.py`.

### Chunked Stream Ingestion
*Definition:* An I/O pattern where incoming network data is read in fixed-size buffers (e.g., 64 KB) rather than loading entire payloads into server memory at once. Prevents memory exhaustion attacks.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/ingestion/validator.py` (`read_and_validate_file_stream`).

### Corrupted File
*Definition:* A document payload whose internal binary or XML structure violates format specifications and causes parser failures during extraction.  
*Status:* **`[IMPLEMENTED]`** — Handled via `CorruptedFileError` (HTTP 422) in `backend/app/core/errors.py`.

### Denial of Service (DoS)
*Definition:* An attack intended to shut down a machine or network, making it inaccessible to intended users by exhausting computing resources (RAM, CPU, disk).  
*Status:* **`[IMPLEMENTED]`** — Mitigated by streaming size limits and format checks.

### Magic Bytes (File Signatures)
*Definition:* Specific constant byte sequences located at the beginning of binary files used to verify actual format independently of client-provided filename extensions.  
*Status:* **`[IMPLEMENTED]`** — Implemented for `%PDF-`, `PK\x03\x04` in `backend/app/ingestion/validator.py`.

### Multipart/Form-Data
*Definition:* An HTTP encoding standard allowing clients to stream binary files and metadata payloads concurrently across boundary markers.  
*Status:* **`[IMPLEMENTED]`** — Implemented via `python-multipart` and FastAPI `UploadFile`.

### Near-Empty Document
*Definition:* A document with less than 10 readable text characters, typically resulting from image-only scans or empty templates.  
*Status:* **`[IMPLEMENTED]`** — Detected in `backend/app/ingestion/extractor.py` and flagged via `warnings`.

### Path Traversal
*Definition:* A directory escape attack where characters like `../` or `..\` are injected into filenames to escape target upload folders and overwrite critical system files.  
*Status:* **`[IMPLEMENTED]`** — Neutralized via sanitization and UUID naming in `backend/app/ingestion/validator.py`.

### Pydantic Settings
*Definition:* A settings management library that parses and validates environment variables from system environments or `.env` files with strict type enforcement.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/core/config.py`.

### Unidirectional Layered Architecture
*Definition:* An architectural pattern where software dependencies flow in a single direction (Route $\rightarrow$ Service $\rightarrow$ Validator/Extractor) to maintain decoupling and testability.  
*Status:* **`[IMPLEMENTED]`** — Maintained across all Day 1, Day 2, and Day 3 backend modules.

---

## Chunking, Embeddings & Vector Storage Terms (Day 2)

### all-MiniLM-L6-v2
*Definition:* A 5-layer SentenceTransformer neural network mapping text into a 384-dimensional dense vector space. Runs locally on CPU with zero API costs.  
*Status:* **`[IMPLEMENTED]`** — Managed via `EmbeddingService` in `backend/app/retrieval/embeddings.py`.

### ChromaDB
*Definition:* An embedded, persistent vector database that stores dense vectors, document texts, and metadata directly on disk, utilizing HNSW graphs for nearest-neighbor search.  
*Status:* **`[IMPLEMENTED]`** — Managed via `VectorStoreManager` in `backend/app/retrieval/vector_store.py`.

### Chunk Index
*Definition:* A 0-based sequential integer recording the position of a chunk within its parent document.  
*Status:* **`[IMPLEMENTED]`** — Attached in `backend/app/ingestion/chunker.py`.

### Chunk Overlap
*Definition:* A sliding window of shared characters (e.g., 50 characters, ~10-20%) across adjacent chunks to maintain semantic continuity across boundaries.  
*Status:* **`[IMPLEMENTED]`** — Configured in `backend/app/core/config.py` (`CHUNK_OVERLAP`).

### Content Hash (Idempotent Deduplication)
*Definition:* A deterministic cryptographic hash (SHA-256) of document text used to identify identical files, prevent duplicate vector entries, and skip redundant embedding computations.  
*Status:* **`[IMPLEMENTED]`** — Computed in `backend/app/ingestion/chunker.py` and checked in `backend/app/retrieval/vector_store.py`.

### Cosine Similarity Space
*Definition:* A geometric metric measuring the cosine of the angle between two vectors ($\frac{A \cdot B}{\|A\| \|B\|}$). Measures conceptual alignment independent of passage length.  
*Status:* **`[IMPLEMENTED]`** — Configured in ChromaDB collection metadata (`{"hnsw:space": "cosine"}`).

### Dense Vector Embedding
*Definition:* A continuous numerical vector where every coordinate captures latent semantic meaning.  
*Status:* **`[IMPLEMENTED]`** — Generated in `backend/app/retrieval/embeddings.py`.

### HNSW (Hierarchical Navigable Small World)
*Definition:* A multi-layer graph data structure used for approximate nearest neighbor search in high-dimensional vector spaces, providing $O(\log N)$ search complexity.  
*Status:* **`[IMPLEMENTED]`** — Embedded within ChromaDB's underlying index engine.

### Page-Aware Chunking
*Definition:* A chunking discipline where text splitting is constrained within physical page boundaries so that every chunk carries its true source `page_number` for citations.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/ingestion/chunker.py`.

### Recursive Character Text Splitter
*Definition:* A text splitter that hierarchically splits on `\n\n`, `\n`, `. `, and ` ` to preserve natural paragraph and sentence boundaries.  
*Status:* **`[IMPLEMENTED]`** — Implemented using `langchain-text-splitters` in `backend/app/ingestion/chunker.py`.

### Semantic Vector Retrieval
*Definition:* Searching an indexed knowledge base by comparing the dense vector representation of a user query against document chunk vectors to retrieve the nearest semantic matches.  
*Status:* **`[IMPLEMENTED]`** — Implemented via `POST /api/v1/search/vector` in `backend/app/api/v1/endpoints/search.py`.

---

## Sparse BM25 & Hybrid Fusion Terms (Day 3)

### BM25 (Best Matching 25)
*Definition:* A probabilistic keyword ranking algorithm that scores documents based on query term frequency, inverse document frequency, and document length normalization.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/retrieval/bm25_index.py`.

### Candidate Multiplier
*Definition:* A multiplier parameter that expands initial candidate pools retrieved from vector and BM25 systems before fusion (e.g., retrieving $2 \times \text{top\_k}$), ensuring cross-system consensus candidates are captured.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/retrieval/hybrid.py`.

### Document Length Normalization ($b$)
*Definition:* The BM25 parameter ($b \in [0, 1]$, default $0.75$) that scales down term frequency scores in disproportionately long documents to prevent verbose passages from dominating search results.  
*Status:* **`[IMPLEMENTED]`** — Embedded in `rank-bm25` configuration.

### Dual-Indexing
*Definition:* The architectural pattern of writing ingested document chunks synchronously to both dense vector storage (ChromaDB) and sparse keyword storage (BM25) to guarantee continuous index parity.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/indexing_service.py`.

### Lucene-Smoothed IDF
*Definition:* The non-negative variant of Inverse Document Frequency: $\text{IDF}(q) = \ln\left(1 + \frac{N - n + 0.5}{n + 0.5}\right)$, adding $1.0$ inside the logarithm to guarantee strictly non-negative scores even on small document collections ($N \le 2$).  
*Status:* **`[IMPLEMENTED]`** — Implemented via class `LuceneBM25` in `backend/app/retrieval/bm25_index.py`.

### Reciprocal Rank Fusion (RRF)
*Definition:* A rank aggregation algorithm combining multiple ranked search lists into a single score: $\sum \frac{1}{k + \text{rank}(d)}$. Operates on ordinal ranks rather than uncalibrated raw scores.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/retrieval/hybrid.py`.

### Retrieval Observability
*Definition:* Transparently recording the individual candidate ranks and raw scores from every underlying retrieval system (`vector_rank`, `vector_score`, `bm25_rank`, `bm25_score`) alongside the fused `rrf_score`.  
*Status:* **`[IMPLEMENTED]`** — Provided via `RetrievalDebugInfo` in `backend/app/schemas/search.py`.

### RRF Smoothing Constant ($k$)
*Definition:* The denominator constant (default $k=60$) in the RRF formula that smooths the score curve across rank positions, preventing top ranks in one retriever from completely overpowering balanced consensus candidates.  
*Status:* **`[IMPLEMENTED]`** — Configured via `core/config.py` (`RRF_K=60`).

### Term Frequency Saturation ($k_1$)
*Definition:* The BM25 parameter (default $k_1=1.5$) that sets an asymptotic upper bound on score gains from repeated term occurrences, preventing keyword-stuffing exploits.  
*Status:* **`[IMPLEMENTED]`** — Configured in `backend/app/retrieval/bm25_index.py`.

---

## Reranking & Grounded Generation Terms (Day 4)

### Bi-Encoder
*Definition:* A neural architecture that maps questions and documents into vector embeddings independently through separate forward passes. Fast for nearest-neighbor search, but lacks token-level cross-attention.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/retrieval/embeddings.py` (`all-MiniLM-L6-v2`).

### Cross-Encoder
*Definition:* A neural architecture that concatenates a query and passage into a single sequence $[q, \text{SEP}, p]$ and computes full bidirectional cross-attention across all tokens. Highly accurate for second-stage passage reranking.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/retrieval/reranker.py` (`cross-encoder/ms-marco-MiniLM-L-6-v2`).

### Evidence Sufficiency Gate
*Definition:* An architectural check evaluated prior to LLM generation that verifies candidate availability and cross-encoder relevance scores. If scores fall below a minimum logit threshold (e.g. $-6.0$), the system short-circuits to an abstention response without invoking the LLM.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py`.

### Explicit Abstention
*Definition:* The system's deliberate refusal to fabricate an answer when retrieved evidence is absent or insufficient, returning a standardized notice: *"The available documents do not provide enough information to answer this question."*  
*Status:* **`[IMPLEMENTED]`** — Implemented across `chat_service.py`, `provider.py`, and `prompts.py`.

### Grounded Answer Generation
*Definition:* Synthesizing natural-language answers strictly constrained to facts present in the retrieved evidence passages, forbidding model extrapolation or outside knowledge.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py` via `SYSTEM_GROUNDING_PROMPT`.

### Pluggable LLM Provider Adapter
*Definition:* An architectural pattern abstracting LLM completion calls behind a polymorphic interface (`BaseLLMProvider`), decoupling business logic from underlying vendor SDKs (Gemini, OpenAI, Mock).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/generation/provider.py`.

### Prompt Injection Defense (Delimited XML)
*Definition:* Enclosing external document text inside `<context><chunk>...</chunk></context>` XML boundaries and sanitizing closing tags to prevent document content from executing as system instructions.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/generation/prompts.py`.

### Server-Side Citation Validation
*Definition:* Extracting model citation markers (e.g., `[chunk_id]`) and strictly verifying them against the actual in-memory map of retrieved context chunks, discarding or flagging any fabricated references.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py`.

---

## Citations, Source Panel & Conversation Terms (Day 5)

### Cascading Deletion
*Definition:* A relational database constraint (`ondelete="CASCADE"`) ensuring that when a parent entity (such as a Conversation session) is deleted, all dependent records (such as child Messages) are automatically pruned from the database.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/db/models.py`.

### Direct Quotation vs. Interpretive Paraphrase
*Definition:* The algorithmic distinction between verbatim quotes excerpted directly from source documents ($\ge 20$ characters) and model-synthesized paraphrases. Vital for legal and regulatory compliance auditing.  
*Status:* **`[IMPLEMENTED]`** — Implemented via n-gram rolling window matcher in `backend/app/services/citation_service.py`.

### Multi-Turn Conversation Memory
*Definition:* Session-aware dialogue state tracking that persists conversation turns in a relational database, reformulates follow-up queries with recent context, and formats message history for the generator.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/conversation_service.py` and `chat_service.py`.

### Query Contextualization
*Definition:* The process of augmenting a brief or pronoun-heavy user query (e.g. *"Who signs off on that?"*) with previous conversation turns to preserve retrieval recall across multi-turn interactions.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py`.

### Relational Metadata Store (SQLite)
*Definition:* An embedded ACID-compliant relational database (`data/nexusai.db`) accessed via SQLAlchemy 2.0 to manage structured entity lifecycles, foreign-key relationships, and conversation history.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/db/session.py`.

### Source Inspector Endpoint
*Definition:* A dedicated HTTP route (`GET /api/v1/citations/{chunk_id}`) that retrieves the un-truncated text, character count, page number, and document metadata of an indexed chunk for interactive UI citation modal inspection.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/api/v1/endpoints/citations.py`.

### Source Panel Item
*Definition:* A dedicated Pydantic model (`SourcePanelItem`) packaging comprehensive evidence attributes for frontend citation sidebars: citation badge index, document ID, filename, page number, snippet, reranker score, and direct quote span.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/schemas/citation.py`.

---

## LangGraph Workflows & Query Routing Terms (Day 6)

### Bounded Read-Only Tools
*Definition:* Tool implementations that provide constrained, read-only data access without shell access, file write capabilities, or external network egress. Prevents prompt injection attacks from compromising the host.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/tools.py`.

### Conditional Edge
*Definition:* A dynamic routing edge in a LangGraph graph that evaluates the current state dictionary and returns a string identifying which downstream node to transition to next.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` (`route_decision`, `check_evidence_decision`).

### Document Summarization Branch
*Definition:* A specialized workflow path in the state machine that loads document chunks sequentially and prompts the model to generate an executive summary, key findings, and action items with verifiable citations.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` and `backend/app/services/workflow_service.py`.

### Evidence Sufficiency Gating
*Definition:* A conditional routing gate in the graph topology that checks if candidate passages exist and whether the top cross-encoder score satisfies the relevance threshold ($\ge -6.0$). If not, execution immediately diverts to an abstention node.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` (`check_evidence_decision`).

### Execution Route Tracing
*Definition:* An observability pattern where each traversed graph node appends its identifier to an execution log (`execution_route: List[str]`), providing a full audit trail of how the answer was synthesized.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` and `backend/app/schemas/workflow.py`.

### Intent Classification & Query Routing
*Definition:* The process of determining user intent from a query (or explicit parameter) and directing execution to the appropriate workflow branch (Q&A, Summarization, or Risk Extraction).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` (`classify_query_node`).

### LangGraph Stateful Orchestration
*Definition:* Orchestrating multi-step, branching LLM workflows using a directed graph (`StateGraph`) with an explicit typed state dictionary, replacing brittle procedural scripts.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py`.

### StateGraph
*Definition:* The core graph data structure provided by LangGraph that manages nodes, edges, conditional branches, and state propagation.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py`.

### Structured Risk Extraction
*Definition:* An automated compliance analysis workflow that inspects document evidence and extracts typed risk records containing category, severity (`HIGH`/`MEDIUM`/`LOW`), description, mitigation, and supporting chunk ID.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/graph.py` and `backend/app/schemas/workflow.py`.

### WorkflowState
*Definition:* A strict `TypedDict` defining all state attributes passed between LangGraph nodes during workflow execution.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/workflows/state.py`.

---

## Evaluation, Benchmarking & Golden Dataset Terms (Day 7)

### 4-Way Retrieval Ablation
*Definition:* An empirical benchmarking methodology that systematically compares four retrieval configurations (Dense Vector-Only, Sparse BM25-Only, Hybrid RRF, and Hybrid + Cross-Encoder Reranking) across the exact same test queries to isolate the quantitative contribution of each algorithmic stage.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/benchmarks.py` (`run_ablation_comparison`).

### Abstention Accuracy
*Definition:* A safety evaluation metric evaluating whether the system successfully triggers explicit abstention (`insufficient_evidence: true`) on negative/unanswerable queries and successfully generates answers on positive queries. Prevents silent hallucinations on out-of-domain prompts.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_abstention_accuracy`).

### Citation Precision & Recall
*Definition:* Quantitative metrics assessing source attribution. Citation Precision measures the ratio of cited chunk identifiers that are truly relevant ($|\text{Cited} \cap \text{Relevant}| / |\text{Cited}|$). Citation Recall measures the fraction of required ground-truth chunks cited ($|\text{Cited} \cap \text{Relevant}| / |\text{Relevant}|$).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py`.

### Context Precision (MAP@K — Mean Average Precision)
*Definition:* An Information Retrieval metric evaluating the rank quality of retrieved passages by penalizing systems where relevant documents appear lower in the candidate list. Computed as $\text{AP}@K = \frac{1}{\min(|\text{Relevant}|, K)} \sum_{k=1}^K \text{Precision}@k \cdot \text{rel}(k)$.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_context_precision`).

### Context Recall
*Definition:* The proportion of all relevant ground-truth passages that are successfully surfaced anywhere in the retrieved candidate pool ($|\text{Retrieved} \cap \text{Relevant}| / |\text{Relevant}|$).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_context_recall`).

### Faithfulness (Claim Support Ratio)
*Definition:* The ratio of atomic claims or sentences in the generated answer that are directly supported by the retrieved context passages, verifying that the model does not hallucinate facts outside the provided evidence.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_faithfulness`).

### Golden Evaluation Dataset
*Definition:* A versioned, curated ground-truth test suite (`backend/evaluation/datasets/v1.jsonl`) pairing enterprise queries with verified ground-truth chunk IDs, document IDs, expected answers, and question type classifications across factual, alphanumeric, multi-hop, summarization, and unanswerable prompts.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/evaluation/datasets/v1.jsonl` and `backend/app/evaluation/dataset.py`.

### Hit@K (Binary Hit Rate)
*Definition:* An Information Retrieval metric returning 1.0 if at least one relevant ground-truth passage appears in the Top-$K$ retrieved candidates, and 0.0 otherwise.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_hit_at_k`).

### Mean Reciprocal Rank (MRR)
*Definition:* A classic ranking metric measuring the reciprocal rank of the first relevant passage retrieved: $\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i^*}$. Highly sensitive to whether the most relevant passage is placed at Rank 1.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_mrr`).

### Proportional Recall@K
*Definition:* The proportion of total ground-truth chunks retrieved within the Top-$K$ candidate list ($|\text{Retrieved}_K \cap \text{Relevant}| / |\text{Relevant}|$).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_recall_at_k`).

### Verbatim Quote Ratio
*Definition:* The percentage of sentences in the generated answer that match verbatim substrings ($\ge 20$ characters) from the retrieved source passages, computed via rolling n-gram window inspection.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/metrics.py` (`calculate_verbatim_quote_ratio`).

---

## Frontend & Copilot User Interface Concepts (Day 8)

### React UI Dashboard
*Definition:* Full-stack frontend single-page application (SPA) providing document management, grounded multi-turn chat, interactive citation inspection, retrieval ablation benchmarking, and runtime system settings.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/` using React 18, Vite 6, TypeScript 5, and Tailwind CSS.

### Click-to-Verify Citation Sidecar
*Definition:* An interactive slide-over drawer or modal (`SourceInspectorModal.tsx`) triggered by clicking citation pills `[chunk_id]`. It fetches full passage text and metadata from `GET /api/v1/citations/{chunk_id}` and highlights verbatim direct quotes.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/src/components/SourceInspectorModal.tsx`.

### Vite Development Reverse Proxy
*Definition:* A local development server proxy configuration in `vite.config.ts` that forwards `/api` requests directly to `http://127.0.0.1:8000`, eliminating CORS preflight latencies and origin mismatch issues during local engineering.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/vite.config.ts`.

### Visual Abstention Guardrail
*Definition:* A high-visibility warning banner in the chat transcript rendered whenever the backend returns `insufficient_evidence: true`. It informs the user that evidence fell below the sufficiency threshold (logit < -6.0) and the copilot refused to speculate.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/src/views/ChatView.tsx`.

### Relational Document Registry
*Definition:* A SQLite table (`DocumentModel`) storing document ID, filename, file format, content hash, ingestion status, chunk count, and timestamps to power the document inventory catalog and lifecycle management.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/db/models.py` and `backend/app/services/document_service.py`.

### Execution Route Breadcrumb
*Definition:* A visible trail of node names displayed on assistant responses recording the exact sequence of LangGraph graph nodes traversed during execution (e.g. `classify_query -> retrieve_and_rerank -> generate_qa`).  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/src/views/ChatView.tsx`.

### Production Docker Containerization
*Definition:* Multi-stage container packaging for both FastAPI backend and Vite frontend with persistent host volume mounts for ChromaDB, BM25, and SQLite state.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`.

### Continuous Integration (GitHub Actions)
*Definition:* Automated CI pipeline running backend pytest suites, frontend TypeScript compilation, and container syntax validation on every commit and pull request.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `.github/workflows/ci.yml`.

### Adversarial Context Injection Defense
*Definition:* Structural XML encapsulation (`<document_context>`), bracket sanitization, and system instruction firewalls neutralizing indirect prompt injection attacks embedded inside ingested documents.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py` and validated in `backend/tests/test_security_hardening.py`.

### Prompt Jailbreak & Tag Breakout Sanitization
*Definition:* String pre-processing stripping faux closing tags (`</document_context>`) from user query payloads to prevent attackers from escaping delimiter boundaries into instruction space.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py` and validated in `backend/tests/test_security_hardening.py`.

### Multi-Stage Container Build
*Definition:* Docker packaging paradigm separating build-time tools (compilers, Node build environments) from runtime execution environments, minimizing attack surface and artifact size.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/Dockerfile` and `frontend/Dockerfile`.

### CPU-Optimized PyTorch Wheel
*Definition:* Installing CPU-only PyTorch wheels (`--index-url https://download.pytorch.org/whl/cpu`) in CPU inference environments, reducing container image size from ~5.5 GB to ~800 MB by eliminating CUDA GPU binaries.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/Dockerfile`.

### Nginx Reverse Proxy & Single-Origin SPA Routing
*Definition:* Production edge routing architecture in `frontend/nginx.conf` that serves compiled Vite static assets with HTML5 history fallback (`try_files $uri $uri/ /index.html;`) and proxies `/api/v1/` internally to FastAPI, eliminating CORS preflight latencies and vulnerabilities.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `frontend/nginx.conf`.

### Deterministic CI Quality Gate
*Definition:* Automated testing philosophy in CI pipelines utilizing offline local embedding models and deterministic mock LLMs to validate the entire suite (67 tests) in seconds with zero cloud API costs or flaky network timeouts.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `.github/workflows/ci.yml` and `backend/tests/test_e2e_integration.py`.

### Unprivileged Non-Root Container Execution
*Definition:* Running container workloads under custom non-root system users (`nexususer` UID 10001; `nginx` worker) with strict directory ownership, mitigating host privilege escalation risks.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/Dockerfile` and `frontend/Dockerfile`.

### Demonstration Runbook
*Definition:* A fully scripted, reproducible operational walkthrough (`docs/DEMO_RUNBOOK.md`) covering 7 end-to-end user scenarios with exact CLI `curl` payloads and UI browser steps, verified programmatically via `backend/tests/test_demo_runbook.py`.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `docs/DEMO_RUNBOOK.md` and `backend/tests/test_demo_runbook.py`.

### Empirical Retrieval Ablation
*Definition:* A systematic benchmark comparing 4 distinct retrieval architectures (Dense vs. Sparse vs. Hybrid RRF vs. Joint Cross-Encoder) across a 25-query golden dataset to measure Recall@K, Hit@K, MRR, Context Precision, and latency percentiles.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/evaluation/benchmarks.py` and documented in `docs/EVALUATION_REPORT.md`.

### Negative Control Abstention
*Definition:* A RAG verification methodology evaluating unanswerable queries on out-of-domain topics to empirically prove that the system abstains deterministically rather than hallucinating when evidence is absent.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/chat_service.py` and validated across 5 golden benchmark test cases.

### Rolling N-Gram Verbatim Quote Span
*Definition:* An algorithmic verification mechanism comparing generated LLM answer text against retrieved passage text using an n-gram sliding window ($\ge 20$ chars) to prove factual attribution and highlight exact quotes in the UI.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `backend/app/services/citation_service.py` and `frontend/src/components/SourceInspectorModal.tsx`.

### Definition of Done Acceptance Matrix
*Definition:* A comprehensive engineering audit checklist verifying all 22 acceptance criteria from Section 18 of the Master Project Blueprint across Product Functionality, GenAI Engineering, Evaluation, and Delivery.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `docs/DEFINITION_OF_DONE_AUDIT.md`.

### Hiring-Focused Portfolio Package
*Definition:* An executive presentation document (`docs/PORTFOLIO_PACKAGE.md`) containing Blueprint Section 19.1 compliant resume bullet points with real measured metrics, an architectural walkthrough script, and an interview defense cheat sheet.  
*Status:* **`[IMPLEMENTED]`** — Implemented in `docs/PORTFOLIO_PACKAGE.md`.

### Final System Delivery & Comprehensive Demonstration Runbook
*Definition:* Production demonstration script, golden sample corpus walkthrough, developer onboarding documentation, and project sign-off.  
*Status:* **`[IMPLEMENTED]`** — Implemented across `docs/DEMO_RUNBOOK.md`, `docs/EVALUATION_REPORT.md`, `docs/PORTFOLIO_PACKAGE.md`, and `docs/DEFINITION_OF_DONE_AUDIT.md`.

---

## Project Completion Status: 100% Implemented & Delivered

All 10 days of planned engineering, architectural modules, automated tests (68/68 passing), container packaging, evaluation benchmarks, and demonstration assets are fully implemented, empirically verified, and production-ready.
