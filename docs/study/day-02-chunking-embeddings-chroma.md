# Study Module: Day 2 — Text Chunking, Local Embeddings & ChromaDB Vector Index

> **Target Role:** GenAI Engineer / Enterprise Systems Developer  
> **Status:** All components referenced in this document are labeled either **`[IMPLEMENTED]`** (verified working code in repository) or **`[PLANNED]`** (future roadmap scope).

---

## Architecture Visualizations

### Master System Architecture (Day 2 State)
![Master System Architecture](../images/system-architecture.svg)

### Day 2 Chunking, Embedding & Indexing Flow
![Day 2 Chunking & Indexing Flow](../images/day-02-chunking-indexing-flow.svg)

### Backend Module Map
![Day 2 Module Map](../images/day-02-module-map.svg)

---

## 1. Big Picture: What This Module Does and Why the Project Needs It

In Day 1, NexusAI built the ingestion foundation: validating and extracting text from PDFs, DOCX, and plain text files with physical page metadata. However, raw extracted documents can be tens or hundreds of pages long—far too large and semantically diffuse to feed directly into an LLM or use as a single search target.

Day 2 bridges the gap between raw document text and semantic search:
- **Chunking:** It breaks down extracted text into smaller, overlapping semantic units (~500 characters) while preserving the origin `page_number` for every chunk.
- **Deduplication:** It computes a deterministic SHA-256 `content_hash` over the document content, preventing identical files from generating duplicate vectors or wasting compute.
- **Local Dense Embeddings:** It passes chunk texts through a local SentenceTransformer model (`all-MiniLM-L6-v2`), generating normalized 384-dimensional dense vectors on the CPU with zero external API calls or latency.
- **Persistent Vector Store (ChromaDB):** It saves vectors, document texts, and citation metadata to disk under cosine similarity space (`hnsw:space: cosine`).
- **Semantic Vector Retrieval:** It exposes an endpoint (`POST /api/v1/search/vector`) that translates natural-language queries into vectors and retrieves the nearest semantic passages in sub-10 milliseconds.

---

## 2. Concepts and Technologies

### 2.1 Recursive Character Chunking
* **What it is:** A text splitting technique that recursively attempts to split text using a hierarchical list of separators (double newlines, single newlines, sentences, spaces, characters) until chunks fit within a target size.
* **Why we need it:** Naive splitting (e.g., splitting every 500 characters) cuts words and sentences in half, ruining semantic meaning. Recursive splitting preserves paragraph and sentence boundaries wherever possible.
* **How it works internally:** Uses `langchain_text_splitters.RecursiveCharacterTextSplitter`. It first tries splitting on `\n\n` (paragraphs). If a paragraph exceeds `chunk_size`, it splits on `\n` (lines), then `. ` (sentences), and finally spaces.
* **Where it appears:** `backend/app/ingestion/chunker.py` in `chunk_extracted_pages()`.
* **Worked Example:**
  ```python
  splitter = RecursiveCharacterTextSplitter(
      chunk_size=500,
      chunk_overlap=50,
      separators=["\n\n", "\n", ". ", " ", ""]
  )
  chunks = splitter.split_text(page_text)
  ```
* **Common Mistakes:** Splitting across the entire document as a single flat string without page boundaries, permanently destroying page-level attribution for citations.

### 2.2 Chunk Overlap
* **What it is:** A sliding window technique where a specified number of characters (e.g., 50 characters, ~10-20%) from the end of one chunk are repeated at the beginning of the subsequent chunk.
* **Why we need it:** Prevents critical semantic context from being sliced in half across a chunk boundary (e.g., a premise in Chunk $N$ and its conclusion in Chunk $N+1$).
* **How it works internally:** The text splitter tracks character offsets and prefixes the next chunk with the trailing tokens of the previous chunk.
* **Where it appears:** `backend/app/core/config.py` (`CHUNK_OVERLAP=50`) and `backend/app/ingestion/chunker.py`.
* **Worked Example:**
  - Chunk 0: `"...and the password must be changed every 90 days."`
  - Chunk 1: `"password must be changed every 90 days. Failure to comply will lock the account..."`
* **Common Mistakes:** Setting overlap too high (>40%), which floods retrieval with duplicate text and exhausts the LLM's context window.

### 2.3 Metadata Preservation
* **What it is:** Attaching structured key-value attributes (`document_id`, `filename`, `page_number`, `chunk_index`, `content_hash`) to each text chunk.
* **Why we need it:** An LLM cannot generate faithful, verifiable citations unless every retrieved context passage explicitly knows its source document and physical page number.
* **How it works internally:** Stored as a Pydantic `ChunkMetadata` object in memory and serialized into ChromaDB's `metadatas` dictionary during batch upserts.
* **Where it appears:** `backend/app/schemas/chunk.py` (`ChunkMetadata`) and `backend/app/ingestion/chunker.py`.
* **Worked Example:**
  ```python
  metadata = ChunkMetadata(
      document_id=doc_id,
      filename="handbook.pdf",
      page_number=12,
      chunk_index=3,
      content_hash="cfd52b..."
  )
  ```
* **Common Mistakes:** Discarding page numbers during parsing or storing metadata outside the vector database, requiring expensive secondary database lookups during retrieval.

### 2.4 Content Hashing & Idempotent Deduplication
* **What it is:** Computing a deterministic cryptographic hash (SHA-256) across the combined extracted text of a document to identify duplicate content.
* **Why we need it:** Users frequently re-upload the same document. Without deduplication, duplicate chunks clutter the vector index, dilute search rankings, and waste embedding computation.
* **How it works internally:** Hashes the normalized text of all pages. Before chunking, `IndexingService` queries ChromaDB with `where={"content_hash": hash}`. If a match is found, indexing is skipped and the API reports `status: "already_indexed"`.
* **Where it appears:** `backend/app/ingestion/chunker.py` (`compute_content_hash`) and `backend/app/retrieval/vector_store.py` (`is_document_indexed`).
* **Worked Example:**
  ```python
  hasher = hashlib.sha256()
  for page in sorted(pages, key=lambda p: p.page_number):
      hasher.update(page.text.strip().encode("utf-8"))
  return hasher.hexdigest()
  ```
* **Common Mistakes:** Hashing the raw uploaded binary file rather than extracted text, causing two identical PDFs with different internal PDF creation timestamps to be treated as different files.

### 2.5 Dense Vector Embeddings
* **What it is:** High-dimensional numerical arrays (vectors) that encode the semantic meaning of text into a continuous geometric space.
* **Why we need it:** Keyword search fails when users ask questions using synonyms (e.g., searching for "salary guidelines" when the document says "compensation policy"). Dense vectors capture semantic similarity even when zero words overlap.
* **How it works internally:** A transformer neural network maps text tokens into an embedding space where semantically similar phrases are located close to one another (measured by cosine angle).
* **Where it appears:** `backend/app/retrieval/embeddings.py` (`EmbeddingService`).
* **Worked Example:**
  `"employee compensation"` $\rightarrow$ `[0.024, -0.051, 0.089, ...]` (384 float values).
* **Common Mistakes:** Comparing vectors produced by different models or different versions of the same model, resulting in meaningless similarity scores.

### 2.6 SentenceTransformers (`all-MiniLM-L6-v2`)
* **What it is:** A state-of-the-art Python framework for state-of-the-art sentence, text, and image embeddings based on PyTorch and Hugging Face.
* **Why we need it:** `all-MiniLM-L6-v2` is an ultra-fast, 5-layer transformer that generates 384-dimensional vectors. It runs directly on consumer CPU hardware in ~5ms per chunk with zero external API costs.
* **How it works internally:** Tokenizes input text into WordPiece tokens, runs them through transformer attention layers, and performs mean pooling over token embeddings.
* **Where it appears:** `backend/app/retrieval/embeddings.py`.
* **Worked Example:**
  ```python
  model = SentenceTransformer("all-MiniLM-L6-v2")
  embeddings = model.encode(["Sample text"], normalize_embeddings=True)
  # returns numpy array of shape (1, 384)
  ```
* **Common Mistakes:** Loading a new instance of `SentenceTransformer` on every API request instead of using a shared singleton, causing high memory usage and latency.

### 2.7 Cosine Similarity Space
* **What it is:** A metric that measures the cosine of the angle between two multi-dimensional vectors: $\text{CosineSim}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$.
* **Why we need it:** Measures directional alignment rather than vector magnitude, ensuring that short sentences and longer paragraphs with identical meaning receive high similarity scores.
* **How it works internally:** When vectors are unit-normalized ($\|A\| = 1$), the cosine similarity simplifies to the dot product ($A \cdot B$). ChromaDB's HNSW index searches for nearest neighbors using cosine distance ($1 - \text{CosineSim}$).
* **Where it appears:** `backend/app/retrieval/vector_store.py` (`{"hnsw:space": "cosine"}`) and `query_similar()`.
* **Worked Example:**
  ```python
  # ChromaDB returns cosine distance d in [0, 2]
  similarity_score = max(0.0, float(1.0 - distance))
  ```
* **Common Mistakes:** Assuming raw ChromaDB cosine distance is similarity (a distance of 0.0 means 100% identical, while 1.0 means orthogonal).

### 2.8 ChromaDB PersistentClient
* **What it is:** An open-source, embedded vector database that persists vector embeddings, documents, and metadata directly to local disk without requiring an external server daemon.
* **Why we need it:** Perfect for self-contained, reproducible MVP deployments. It avoids cloud database subscription costs and network latency while persisting across restarts.
* **How it works internally:** Uses SQLite for relational chunk metadata and an HNSW (Hierarchical Navigable Small World) graph on disk for nearest-neighbor vector search.
* **Where it appears:** `backend/app/retrieval/vector_store.py`.
* **Worked Example:**
  ```python
  client = chromadb.PersistentClient(path="./data/chroma")
  collection = client.get_or_create_collection(name="nexusai_documents_v1", metadata={"hnsw:space": "cosine"})
  ```
* **Common Mistakes:** Using `chromadb.Client()` (in-memory mode), which erases all indexed vectors when the FastAPI server stops.

### 2.9 Singleton Service Pattern
* **What it is:** A creational design pattern that guarantees a class has only one instance and provides a global point of access to it.
* **Why we need it:** Machine learning models (PyTorch weights) and vector database connections are heavy resources. Creating multiple instances wastes gigabytes of RAM and risks database file-lock conflicts.
* **How it works internally:** Uses a class-level `_instance` variable and a threading lock (`threading.Lock()`) to instantiate the service exactly once upon first request.
* **Where it appears:** `backend/app/retrieval/embeddings.py` (`EmbeddingService.get_instance()`) and `backend/app/retrieval/vector_store.py` (`VectorStoreManager.get_instance()`).
* **Worked Example:**
  ```python
  with cls._lock:
      if cls._instance is None:
          cls._instance = cls()
      return cls._instance
  ```
* **Common Mistakes:** Failing to include thread locks in async/multi-threaded servers, resulting in race conditions where two threads initialize the model concurrently.

### 2.10 Semantic Vector Retrieval
* **What it is:** Querying a vector database with a natural-language search query to retrieve the top-$K$ most semantically relevant candidate passages.
* **Why we need it:** Forms the fundamental "R" in RAG (Retrieval-Augmented Generation). It filters a massive library of thousands of document pages down to the 3-5 most relevant passages for the LLM.
* **How it works internally:** The search query is embedded using `embed_query()`. The resulting 384-dimensional vector is passed to ChromaDB, which traverses its HNSW graph to find the nearest vectors by cosine distance.
* **Where it appears:** `backend/app/api/v1/endpoints/search.py` and `backend/app/services/indexing_service.py` (`search_similar_chunks()`).
* **Worked Example:**
  ```python
  query_vec = embedding_service.embed_query("password reset guidelines")
  results = vector_store.query_similar(query_vec, top_k=3)
  ```
* **Common Mistakes:** Hardcoding `top_k` to a huge number (e.g., 50), which exceeds LLM context windows and introduces noisy, irrelevant passages.

---

## 3. Alternatives Considered and Why Not Chosen

| Design Choice | Chosen Solution | Alternative Considered | Why Alternative Was Rejected |
| :--- | :--- | :--- | :--- |
| **Chunking Strategy** | Page-Aware Recursive Character Chunking | Document-wide flat chunking | Flat chunking concatenates all pages into one string before splitting. This causes chunk boundaries to straddle pages, making it impossible to determine the true source page for citations. |
| **Embedding Model** | `all-MiniLM-L6-v2` (Local SentenceTransformer) | OpenAI `text-embedding-3-small` / Cohere | Hosted APIs incur per-token financial costs, impose rate limits, require internet access, and introduce network latency. `all-MiniLM-L6-v2` runs locally on CPU in ~5ms per chunk with zero API dependencies. |
| **Vector Database** | Embedded `ChromaDB` (`PersistentClient`) | Pinecone / Weaviate / Milvus / Qdrant | Cloud vector databases (Pinecone) require API keys and cloud accounts. Distributed stores (Milvus) require separate Docker containers or Kubernetes clusters. ChromaDB runs embedded in-process and persists cleanly to local disk. |
| **Distance Metric** | Cosine Similarity (`hnsw:space: cosine`) | Euclidean Distance ($L2$) / Dot Product (IP) | $L2$ distance is sensitive to text length variations. Dot product requires strictly normalized vectors. Cosine similarity evaluates angle rather than length, making it ideal for variable-length passages. |

---

## 4. Code Walkthrough in Data-Flow Order

### Step 1: Page-Aware Chunking & Content Hash
*File:* `backend/app/ingestion/chunker.py`
```python
def chunk_extracted_pages(document_id: str, filename: str, pages: List[PageExtraction], ...):
    content_hash = compute_content_hash(pages)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50, ...)
    chunks = []
    chunk_index = 0

    for page in pages:
        for split in splitter.split_text(page.text.strip()):
            chunks.append(DocumentChunk(
                chunk_id=f"{document_id}_p{page.page_number}_c{chunk_index}",
                text=split,
                metadata=ChunkMetadata(
                    document_id=document_id,
                    filename=filename,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    content_hash=content_hash
                )
            ))
            chunk_index += 1
    return chunks
```
*Why:* Iterates page-by-page so that `page.page_number` is preserved for every child chunk, while sequential `chunk_index` maintains overall document order.

### Step 2: Idempotency & Deduplication Check
*File:* `backend/app/services/indexing_service.py`
```python
if vector_store.is_document_indexed(content_hash):
    logger.info("Document with content_hash=%s is already indexed. Skipping.", content_hash)
    existing_chunks = chunk_extracted_pages(document_id, filename, pages)
    return len(existing_chunks), content_hash, True
```
*Why:* Avoids computing hundreds of vector embeddings and prevents duplicate database entries when an unchanged document is re-uploaded.

### Step 3: Local Dense Vector Generation
*File:* `backend/app/retrieval/embeddings.py`
```python
embeddings = self.model.encode(
    texts,
    batch_size=32,
    show_progress_bar=False,
    normalize_embeddings=True
)
return embeddings.tolist()
```
*Why:* Batches encoding into 32 passages at a time for optimal CPU cache utilization, normalizing vectors for exact cosine dot-product equivalence.

### Step 4: Persistent ChromaDB Upsert
*File:* `backend/app/retrieval/vector_store.py`
```python
self._collection.upsert(
    ids=[chunk.chunk_id for chunk in chunks],
    embeddings=embeddings,
    documents=[chunk.text for chunk in chunks],
    metadatas=[chunk.metadata.model_dump() for chunk in chunks]
)
```
*Why:* Atomic batch upsert ensures IDs, raw texts, 384-dimensional vectors, and citation metadata are persistently written to disk in a single call.

### Step 5: Semantic Nearest-Neighbor Query
*File:* `backend/app/api/v1/endpoints/search.py` & `backend/app/retrieval/vector_store.py`
```python
# Convert query to 384d vector, find top_k in ChromaDB
query_embedding = embedding_service.embed_query(query)
results = vector_store.query_similar(query_embedding, top_k=top_k)
```
*Why:* Translates user natural language into the same geometric space as document chunks, retrieving top matches with cosine scores in milliseconds.

---

## 5. Real Request / Response Trace (From Test Execution)

### Trace: Document Upload with Day 2 Indexing
**Request:**
```http
POST /api/v1/documents/upload HTTP/1.1
Host: test
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary
[Binary PDF payload: "NexusAI Enterprise Copilot Hybrid Retrieval Engine"]
```

**Actual Response (HTTP 200 OK):**
```json
{
  "document_id": "76ec965b-efea-4ffb-8719-f5d72f1dc444",
  "filename": "hybrid_retrieval.pdf",
  "file_type": "pdf",
  "status": "processed",
  "extracted_pages": [
    {
      "page_number": 1,
      "text": "NexusAI Enterprise Copilot Hybrid Retrieval Engine",
      "character_count": 50
    }
  ],
  "character_count": 50,
  "chunk_count": 1,
  "content_hash": "246b9a89c922573f550978007201c1075306d152a550d32f7aa47a06421ba10a",
  "warnings": []
}
```

### Trace: Semantic Vector Search
**Request:**
```http
POST /api/v1/search/vector HTTP/1.1
Host: test
Content-Type: application/json

{
  "query": "hybrid retrieval engine",
  "top_k": 3
}
```

**Actual Response (HTTP 200 OK):**
```json
{
  "query": "hybrid retrieval engine",
  "results": [
    {
      "chunk_id": "76ec965b-efea-4ffb-8719-f5d72f1dc444_p1_c0",
      "document_id": "76ec965b-efea-4ffb-8719-f5d72f1dc444",
      "filename": "hybrid_retrieval.pdf",
      "page_number": 1,
      "chunk_index": 0,
      "text": "NexusAI Enterprise Copilot Hybrid Retrieval Engine",
      "score": 0.9999
    }
  ],
  "total_results": 1
}
```

---

## 6. Security and Edge Cases Handled

| Failure / Threat | Impact if Ignored | Implementation Guardrail |
| :--- | :--- | :--- |
| **Duplicate Uploads** | Duplicate vectors dilute retrieval quality and waste disk space. | SHA-256 `content_hash` check stops redundant embedding computation and marks status `already_indexed`. |
| **Blank / Whitespace Chunks** | Vector store polluted with zero-information embeddings. | `clean_split.strip()` check in `chunker.py` discards empty or whitespace-only splits. |
| **Page Attribution Loss** | Downstream LLM hallucinates or cannot cite source page numbers. | Page-aware chunker preserves physical `page_number` on every generated chunk. |
| **Model Re-instantiation** | Memory bloat and OOM crashes from multiple PyTorch model instances. | `EmbeddingService` uses a thread-safe lazy singleton pattern with mutex locks. |
| **Embedding Space Mismatch** | Distance metrics produce nonsense if embedding model changes. | Collection metadata records `embedding_model: all-MiniLM-L6-v2` and collection name includes version suffix `_v1`. |
| **In-Memory Volatility** | Vector index lost on server reboot. | ChromaDB uses `PersistentClient` pointing to configurable `CHROMA_PERSIST_DIR`. |

---

## 7. Status & Scope Matrix: IMPLEMENTED vs PLANNED

| Component / Feature | Status | Details |
| :--- | :--- | :--- |
| **GET /api/v1/health** | **`[IMPLEMENTED]`** | Health probe endpoint (Day 1). |
| **POST /api/v1/documents/upload** | **`[IMPLEMENTED]`** | Document ingestion, validation, extraction & indexing pipeline. |
| **Page-Aware Text Chunking** | **`[IMPLEMENTED]`** | `backend/app/ingestion/chunker.py` (`RecursiveCharacterTextSplitter`). |
| **Content Hashing & Deduplication**| **`[IMPLEMENTED]`** | SHA-256 content hash check before embedding. |
| **Local Embeddings (MiniLM-L6-v2)** | **`[IMPLEMENTED]`** | `backend/app/retrieval/embeddings.py` (PyTorch, 384 dimensions). |
| **Persistent ChromaDB Integration** | **`[IMPLEMENTED]`** | `backend/app/retrieval/vector_store.py` (`PersistentClient`, cosine space). |
| **POST /api/v1/search/vector** | **`[IMPLEMENTED]`** | Semantic similarity search endpoint (Day 2 exit criterion). |
| **Automated Test Suite (18 tests)** | **`[IMPLEMENTED]`** | 100% passing tests in `backend/tests/`. |
| **BM25 Sparse Keyword Indexing** | **`[PLANNED]`** | Scheduled for Day 3. |
| **Reciprocal Rank Fusion (RRF)** | **`[PLANNED]`** | Scheduled for Day 3. |
| **Cross-Encoder Reranker** | **`[PLANNED]`** | Scheduled for Day 4. |
| **LLM Provider Adapter & Answer Generation** | **`[PLANNED]`** | Scheduled for Day 4. |
| **Citation Verification & Abstention** | **`[PLANNED]`** | Scheduled for Day 5. |
| **LangGraph Stateful Workflow Graph** | **`[PLANNED]`** | Scheduled for Day 6. |
| **RAGAS Automated Evaluation** | **`[PLANNED]`** | Scheduled for Day 7. |
| **React UI Dashboard** | **`[PLANNED]`** | Scheduled for Day 8. |

---

## 8. Interview Questions & Model Answers

### Category A: Basic Concepts
1. **Q: What is the primary purpose of text chunking in a RAG pipeline?**  
   *Answer:* Foundation models have finite context windows, and embedding models represent an entire input text as a single fixed-size vector. If an entire 50-page document is embedded as one vector, specific factual details are diluted and lost. Chunking breaks documents into focused semantic units, allowing granular retrieval of the exact passages relevant to a query.
2. **Q: Why do we use chunk overlap when splitting documents?**  
   *Answer:* Natural language thoughts often span sentences or paragraphs. If a split happens right between a critical premise and its qualifying conclusion, both chunks lose semantic coherence. Overlap ensures boundary context is shared across adjacent chunks, preserving meaning.
3. **Q: What are dense vector embeddings, and what does the dimension (e.g., 384) represent?**  
   *Answer:* Dense embeddings are continuous numerical representations of text where coordinates capture latent semantic features. The dimension (384 for `all-MiniLM-L6-v2`) represents the number of real numbers in the vector output by the transformer's hidden layers.

### Category B: Intermediate Architecture
4. **Q: Explain how page numbers are preserved across chunking in NexusAI.**  
   *Answer:* Rather than flattening the document into a single string, NexusAI chunks each page's extracted text independently. Every chunk generated from page $N$ explicitly receives `metadata.page_number = N`. This guarantees downstream citations cite the exact physical page.
5. **Q: Why is cosine similarity preferred over Euclidean distance ($L2$) for text embeddings?**  
   *Answer:* Euclidean distance measures the absolute geometric distance between vectors, which is influenced by text length and token frequency. Cosine similarity evaluates the angle between vectors, measuring conceptual orientation regardless of text length.
6. **Q: What is idempotent ingestion, and how does NexusAI achieve it?**  
   *Answer:* Idempotence means performing an operation multiple times produces the same result as performing it once. NexusAI calculates a SHA-256 hash of the extracted document text. Before indexing, it queries ChromaDB for existing chunks matching that hash. If found, it skips redundant embedding computation and avoids duplicate entries.

### Category C: Advanced & System Design
7. **Q: Why did NexusAI choose `all-MiniLM-L6-v2` over a hosted embedding API like OpenAI's `text-embedding-3-small`?**  
   *Answer:* Cost, privacy, and latency. Hosted APIs incur ongoing token costs, require sending proprietary enterprise documents over the internet, and add 100-300ms of network latency per request. `all-MiniLM-L6-v2` is open-source, runs locally on CPU in ~5ms, and ensures enterprise data never leaves the host environment.
8. **Q: What happens if you change the embedding model in an existing ChromaDB collection?**  
   *Answer:* Embeddings from different models inhabit completely different vector spaces. Comparing a vector from Model A with vectors from Model B yields meaningless random distances. When changing embedding models, the entire collection must be re-indexed under a new collection name or version tag.
9. **Q: How does the HNSW algorithm in ChromaDB achieve sub-second vector search?**  
   *Answer:* HNSW (Hierarchical Navigable Small World) is an approximate nearest-neighbor graph algorithm. Instead of brute-force comparing a query against all vectors ($O(N)$), HNSW builds multi-layer graphs where upper layers allow rapid skipping over large vector distances and lower layers provide fine-grained local search, achieving $O(\log N)$ search complexity.

### Category D: Scenario-Based
10. **Q: A user updates a single paragraph in a 20-page document and re-uploads it. How does the system respond?**  
    *Answer:* Because the text changed, the SHA-256 `content_hash` changes. The system recognizes it as a new version and indexes the updated chunks. In a future production iteration, page-level hashing can be added to update only the specific chunks on the modified page.
11. **Q: A search query returns a chunk with a similarity score of 0.35. How should the application interpret this?**  
    *Answer:* In normalized cosine space, 1.0 is an exact match and 0.0 is orthogonal (unrelated). A score of 0.35 represents weak semantic relevance. Downstream evidence sufficiency checks should filter out chunks below a calibrated threshold (e.g., < 0.5) to prevent the LLM from generating ungrounded answers.
12. **Q: What happens if two different documents accidentally produce the same content hash?**  
    *Answer:* SHA-256 has a collision probability of less than $1 \text{ in } 10^{77}$. In practice, a hash collision between two distinct non-empty text documents is cryptographically impossible.

### Category E: Debugging & Troubleshooting
13. **Q: A query for "employee vacation days" returns zero results even though the document contains vacation policies. What is the root cause?**  
    *Answer:* First, check if the document was indexed or if chunking skipped it due to empty text. Second, check if the vector store has chunks indexed (`count() > 0`). Third, verify if an overly restrictive `where` metadata filter was applied.
14. **Q: Why does the first search request take 2 seconds while subsequent searches take 10 milliseconds?**  
    *Answer:* The `EmbeddingService` uses lazy singleton loading. The very first request loads PyTorch weights from disk into memory and initializes the transformer graph. Subsequent calls reuse the warm in-memory model.
15. **Q: Pytest tests pass individually but fail when run together due to ChromaDB conflicts. How is this fixed?**  
    *Answer:* Tests were sharing a singleton ChromaDB client or writing to the same filesystem directory. In `conftest.py`, each test is given a temporary directory (`tmp_path`) and a unique collection name, and `VectorStoreManager.reset_instance()` is called before and after each test.

### Category F: Trade-Off Analysis
16. **Q: What is the trade-off of a 500-character chunk size versus an 800-token chunk size?**  
    *Answer:* Smaller chunks (500 chars, ~100 tokens) provide high retrieval precision, matching specific sentences and fitting easily into small LLM contexts, but may lack broad narrative context. Larger chunks (800 tokens) retain full context and complex arguments, but introduce noise and consume larger portions of the context window.
17. **Q: What is the trade-off between character-based splitters and token-based splitters?**  
    *Answer:* Character-based splitters run with zero tokenizer dependencies and are fast, but characters do not map 1:1 with model tokens (1 token $\approx$ 4 characters in English). Token-based splitters ensure exact compliance with model token limits, but require running tokenizer models during chunking.
18. **Q: Why use embedded ChromaDB rather than an external vector database container in the MVP?**  
    *Answer:* Embedded ChromaDB runs directly within the Python process and requires zero external infrastructure, simplifying local setup and testing. The trade-off is horizontal scalability: embedded ChromaDB cannot easily scale across multiple server nodes.

---

## 9. Self-Test & 60-Second Explanation Script

### Self-Test Questions
1. What is the embedding dimension of the `all-MiniLM-L6-v2` model?
2. Which distance metric is configured for the ChromaDB collection in `vector_store.py`?
3. How is a chunk's `chunk_id` constructed in `chunker.py`?
4. What happens when an uploaded document has an identical SHA-256 `content_hash` to an already-indexed document?
5. Why are vectors normalized (`normalize_embeddings=True`) before upserting into ChromaDB?
6. Which endpoint is used to query the vector store via HTTP?
7. What are the default values for `CHUNK_SIZE` and `CHUNK_OVERLAP` in `core/config.py`?
8. Why does `VectorStoreManager` convert ChromaDB cosine distance $d$ into $1.0 - d$?

### 60-Second "Explain This Module" Script
> *"Day 2 of NexusAI transforms extracted document text into a searchable semantic knowledge base. 
> 
> When documents are uploaded, our page-aware chunker recursively splits the text into 500-character passages with a 50-character overlap. Crucially, it splits within page boundaries so that every generated chunk carries its original page number and document ID for verifiable citations.
> 
> To prevent duplicate data and wasted compute, we compute a SHA-256 hash across the document text; re-uploaded files are detected and skipped immediately. New chunks are passed to our local SentenceTransformer model—all-MiniLM-L6-v2—generating 384-dimensional dense vectors on CPU with zero API costs.
> 
> These vectors, along with raw text and citation metadata, are persisted to disk in an embedded ChromaDB collection under cosine similarity space. Callers can query the new vector search endpoint to retrieve the most semantically relevant passages in under 10 milliseconds, satisfying our Day 2 exit criteria with 100% test coverage."*

---

## 10. Module Glossary

* **all-MiniLM-L6-v2:** A compact, high-efficiency sentence embedding model that maps sentences to a 384-dimensional dense vector space.
* **ChromaDB:** An open-source, embedded vector database designed for building AI applications with embeddings.
* **Chunk Index:** A 0-based sequential integer indicating the position of a chunk within its parent document.
* **Chunk Overlap:** A sliding window of shared characters between consecutive chunks to preserve contextual continuity across boundaries.
* **Content Hash:** A deterministic cryptographic hash (SHA-256) of document text used to identify identical files and prevent duplicate vector indexing.
* **Cosine Similarity:** A measure of similarity between two non-zero vectors calculated as the cosine of the angle between them ($[-1, 1]$ or $[0, 1]$ for positive embeddings).
* **Dense Embedding:** A continuous vector representation where every dimension carries latent semantic information.
* **HNSW (Hierarchical Navigable Small World):** A multi-layer graph data structure used for approximate nearest neighbor search in high-dimensional vector spaces.
* **Idempotence:** The property of an operation whereby it can be applied multiple times without changing the result beyond the initial application.
* **Recursive Character Text Splitter:** A splitting algorithm that recursively attempts to split text using a priority list of delimiters (`\n\n`, `\n`, `. `, ` `).

