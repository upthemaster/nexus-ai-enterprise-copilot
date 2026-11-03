"""
Sparse BM25 keyword index implementation using rank-bm25 with Lucene-smoothed IDF.

Why: Dense semantic embeddings excel at paraphrases but frequently fail on exact
technical codes, policy identifiers (e.g. 'POL-402'), dates, and uncommon terms.
BM25 provides exact sparse token matching to complement dense vector retrieval.
"""

import math
import json
import re
import threading
import logging
from pathlib import Path
from typing import List, Optional, Set
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.schemas.chunk import DocumentChunk
from app.schemas.search import BM25SearchResultItem

logger = logging.getLogger("nexusai.bm25")


class LuceneBM25(BM25Okapi):
    """
    BM25 implementation using the Apache Lucene / Elasticsearch non-negative IDF formula:
    IDF(q) = ln(1 + (N - n + 0.5) / (n + 0.5))
    
    Why: Standard Robertson-Spärck Jones BM25 produces 0.0 or negative IDF values when
    corpus sizes are small (N <= 2) or when terms appear in >= 50% of documents.
    Lucene's smoothed formula guarantees positive IDF for all valid matches, ensuring
    reliable exact matching across corpora of any size.
    """

    def _calc_idf(self, nd):
        for word, freq in nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


def tokenize_text(text: str) -> List[str]:
    """
    Tokenize text for BM25 keyword matching.
    
    Why: Lowercases and preserves hyphenated technical tokens (e.g., 'pol-402', 'iso-27001')
    and alphanumeric identifiers critical in enterprise documentation.
    """
    if not text:
        return []
    # Match alphanumeric sequences including embedded hyphens
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
    return tokens


class BM25IndexManager:
    """
    Manages the sparse BM25 index, in-memory chunk corpus, and disk persistence.
    """
    _instance: Optional["BM25IndexManager"] = None
    _lock = threading.Lock()

    def __init__(self, persist_path: Optional[str] = None):
        self._persist_path = Path(persist_path or settings.BM25_PERSIST_PATH).resolve()
        self._chunks: List[DocumentChunk] = []
        self._tokenized_corpus: List[List[str]] = []
        self._bm25: Optional[LuceneBM25] = None
        self._indexed_hashes: Set[str] = set()

        self._load_from_disk()

    @classmethod
    def get_instance(cls) -> "BM25IndexManager":
        """
        Thread-safe singleton accessor.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton for test isolation.
        """
        with cls._lock:
            cls._instance = None

    def count(self) -> int:
        """
        Return the total number of chunks in the BM25 corpus.
        """
        return len(self._chunks)

    def is_document_indexed(self, content_hash: str) -> bool:
        """
        Check if a document with this content_hash is already indexed in the BM25 corpus.
        """
        return content_hash in self._indexed_hashes

    def get_chunk_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """
        Retrieve a chunk from the BM25 corpus by its chunk_id.
        """
        for chunk in self._chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """
        Retrieve all chunks belonging to a document from the BM25 corpus, sorted by chunk_index.
        """
        doc_chunks = [c for c in self._chunks if c.metadata.document_id == document_id]
        doc_chunks.sort(key=lambda x: x.metadata.chunk_index)
        return doc_chunks

    def _rebuild_index(self) -> None:
        """
        Recompute BM25 inverted index statistics from the tokenized corpus.
        """
        if self._tokenized_corpus:
            self._bm25 = LuceneBM25(self._tokenized_corpus)
        else:
            self._bm25 = None

    def _save_to_disk(self) -> None:
        """
        Persist the chunk corpus to local disk so keyword search survives restarts.
        """
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            serialized_chunks = [chunk.model_dump() for chunk in self._chunks]
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(serialized_chunks, f, ensure_ascii=False, indent=2)
            logger.info("Persisted %d BM25 chunks to %s", len(self._chunks), self._persist_path)
        except Exception as exc:
            logger.error("Failed to persist BM25 index to disk: %s", exc)

    def _load_from_disk(self) -> None:
        """
        Load corpus from disk if previously saved.
        """
        if not self._persist_path.exists():
            return

        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            self._chunks = [DocumentChunk(**item) for item in raw_data]
            self._tokenized_corpus = [tokenize_text(c.text) for c in self._chunks]
            self._indexed_hashes = {c.metadata.content_hash for c in self._chunks}
            self._rebuild_index()
            logger.info("Loaded %d BM25 chunks from %s", len(self._chunks), self._persist_path)
        except Exception as exc:
            logger.error("Failed to load BM25 index from disk: %s", exc)

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Add a batch of chunks to the BM25 index and persist to disk.
        """
        if not chunks:
            return 0

        # Avoid duplicates within same batch or already present
        new_chunks = [c for c in chunks if c.chunk_id not in {ex.chunk_id for ex in self._chunks}]
        if not new_chunks:
            return 0

        for chunk in new_chunks:
            self._chunks.append(chunk)
            self._tokenized_corpus.append(tokenize_text(chunk.text))
            self._indexed_hashes.add(chunk.metadata.content_hash)

        self._rebuild_index()
        self._save_to_disk()
        logger.info("Added %d chunks to BM25 index. Total corpus: %d", len(new_chunks), len(self._chunks))
        return len(new_chunks)

    def query(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[BM25SearchResultItem]:
        """
        Execute sparse keyword search across the chunk corpus.
        """
        tokenized_query = tokenize_text(query)
        if not tokenized_query or not self._bm25 or not self._chunks:
            return []

        raw_scores = self._bm25.get_scores(tokenized_query)
        scored_candidates = []

        for idx, score in enumerate(raw_scores):
            # Only consider non-zero scores
            if score <= 0.0:
                continue

            chunk = self._chunks[idx]
            if document_id and chunk.metadata.document_id != document_id:
                continue

            scored_candidates.append((chunk, float(score)))

        # Sort by BM25 score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored_candidates[:top_k]

        return [
            BM25SearchResultItem(
                chunk_id=chunk.chunk_id,
                document_id=chunk.metadata.document_id,
                filename=chunk.metadata.filename,
                page_number=chunk.metadata.page_number,
                chunk_index=chunk.metadata.chunk_index,
                text=chunk.text,
                score=round(score, 4)
            )
            for chunk, score in top_candidates
        ]


def get_bm25_manager() -> BM25IndexManager:
    return BM25IndexManager.get_instance()
