"""
Persistent ChromaDB vector store integration.

Why: ChromaDB provides embedded, persistent vector storage requiring no separate
database daemon for local MVP deployments. Storing dense vectors with source metadata
enables sub-second top-K semantic nearest-neighbor retrieval.
"""

import threading
import logging
from typing import List, Optional, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.schemas.chunk import DocumentChunk, VectorSearchResultItem

logger = logging.getLogger("nexusai.vector_store")


class VectorStoreManager:
    """
    Manages persistent ChromaDB collections, chunk upserts, and vector similarity queries.
    
    Why: Centralizing vector operations in a dedicated manager ensures consistent
    distance space configuration (cosine), idempotent deduplication, and reliable
    persistence across server reboots.
    """
    _instance: Optional["VectorStoreManager"] = None
    _lock = threading.Lock()

    def __init__(self, persist_dir: Optional[str] = None, collection_name: Optional[str] = None):
        self._persist_dir = persist_dir or str(settings.chroma_persist_path)
        self._collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        
        logger.info(
            "Initializing persistent ChromaDB client at: %s [collection: %s]",
            self._persist_dir,
            self._collection_name
        )
        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        # Create or retrieve collection with cosine distance metric
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": settings.EMBEDDING_MODEL_NAME
            }
        )

    @classmethod
    def get_instance(cls) -> "VectorStoreManager":
        """
        Thread-safe singleton accessor for the default persistent collection.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton (used in test fixtures to point to fresh temporary storage).
        """
        with cls._lock:
            cls._instance = None

    @property
    def collection(self):
        return self._collection

    def count(self) -> int:
        """
        Return the total number of indexable chunks in the collection.
        """
        return self._collection.count()

    def is_document_indexed(self, content_hash: str) -> bool:
        """
        Check if a document with this identical content_hash is already indexed.
        
        Why: Prevents redundant embedding computation and prevents duplicate chunks
        from skewing similarity rankings when identical files are re-uploaded.
        """
        if not content_hash:
            return False
        existing = self._collection.get(
            where={"content_hash": content_hash},
            limit=1
        )
        return bool(existing and existing["ids"])

    def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> int:
        """
        Batch upsert document chunks and their precomputed embeddings into ChromaDB.
        """
        if not chunks:
            return 0

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata.model_dump() for chunk in chunks]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        logger.info("Upserted %d chunks into collection '%s'", len(chunks), self._collection_name)
        return len(chunks)

    def query_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[VectorSearchResultItem]:
        """
        Query the vector index for the top_k most similar chunks.
        
        Why: ChromaDB with cosine metric returns cosine distance (0.0 to 2.0).
        Converting to similarity score (1.0 - distance) provides intuitive 0.0-1.0
        relevance metrics for callers and evaluation runners.
        """
        if not query_embedding or self.count() == 0:
            return []

        where_filter: Optional[Dict[str, Any]] = None
        if document_id:
            where_filter = {"document_id": document_id}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        search_results: List[VectorSearchResultItem] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return search_results

        ids = results["ids"][0]
        docs = results["documents"][0] if results["documents"] else [""] * len(ids)
        metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
        distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)

        for chunk_id, text, meta, dist in zip(ids, docs, metas, distances):
            # Convert cosine distance to cosine similarity: sim = max(0.0, 1.0 - distance)
            similarity_score = max(0.0, float(1.0 - dist))
            search_results.append(
                VectorSearchResultItem(
                    chunk_id=chunk_id,
                    document_id=str(meta.get("document_id", "")),
                    filename=str(meta.get("filename", "")),
                    page_number=int(meta.get("page_number", 1)),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    text=text or "",
                    score=round(similarity_score, 4)
                )
            )

        return search_results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[VectorSearchResultItem]:
        """
        Fetch a single chunk by its chunk_id for source inspection and citation verification.
        """
        if not chunk_id or self.count() == 0:
            return None

        try:
            result = self._collection.get(
                ids=[chunk_id],
                include=["documents", "metadatas"]
            )
            if not result or not result["ids"] or len(result["ids"]) == 0:
                return None

            meta = result["metadatas"][0] if result["metadatas"] else {}
            text = result["documents"][0] if result["documents"] else ""

            return VectorSearchResultItem(
                chunk_id=chunk_id,
                document_id=str(meta.get("document_id", "")),
                filename=str(meta.get("filename", "")),
                page_number=int(meta.get("page_number", 1)),
                chunk_index=int(meta.get("chunk_index", 0)),
                text=text,
                score=1.0
            )
        except Exception as e:
            logger.warning("Error fetching chunk_id=%s from ChromaDB: %s", chunk_id, e)
            return None

    def get_chunks_by_document(self, document_id: str) -> List[VectorSearchResultItem]:
        """
        Fetch all chunks associated with a specific document_id, sorted by chunk_index.
        Used by summarization, risk extraction, and document analysis workflows.
        """
        if not document_id or self.count() == 0:
            return []

        try:
            results = self._collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"]
            )
            if not results or not results["ids"]:
                return []

            items: List[VectorSearchResultItem] = []
            for chunk_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
                items.append(
                    VectorSearchResultItem(
                        chunk_id=chunk_id,
                        document_id=str(meta.get("document_id", "")),
                        filename=str(meta.get("filename", "")),
                        page_number=int(meta.get("page_number", 1)),
                        chunk_index=int(meta.get("chunk_index", 0)),
                        text=doc or "",
                        score=1.0
                    )
                )

            # Sort sequentially by chunk_index so text reads in logical document order
            items.sort(key=lambda x: x.chunk_index)
            return items
        except Exception as e:
            logger.warning("Error fetching chunks for document_id=%s from ChromaDB: %s", document_id, e)
            return []


# Global accessor function
def get_vector_store() -> VectorStoreManager:
    return VectorStoreManager.get_instance()

