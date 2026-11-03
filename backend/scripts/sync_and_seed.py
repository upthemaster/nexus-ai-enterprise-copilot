import sys
import os
import uuid
import sqlite3
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, "backend")

from app.core.config import settings
from app.services.indexing_service import IndexingService
from app.ingestion.extractor import extract_document_text
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager

def sync_and_seed():
    db_path = settings.sqlite_db_path
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Inspect existing Chroma documents
    vector_store = get_vector_store()
    coll = vector_store._collection
    total_chunks = coll.count()
    print(f"Current Chroma chunks: {total_chunks}")
    
    chroma_doc_ids = set()
    if total_chunks > 0:
        metas = coll.get(include=["metadatas"])["metadatas"]
        for m in metas:
            if "document_id" in m:
                chroma_doc_ids.add(m["document_id"])
    print(f"Valid document IDs in Chroma: {chroma_doc_ids}")
    
    # 2. Clean out orphaned documents from SQLite (leaving only ones that exist in Chroma)
    cur.execute("SELECT id, filename FROM documents")
    all_db_docs = cur.fetchall()
    orphans = [doc_id for doc_id, fn in all_db_docs if doc_id not in chroma_doc_ids]
    print(f"Found {len(orphans)} orphaned document records in SQLite. Removing them...")
    for doc_id in orphans:
        cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    
    # 3. Seed demo sample documents if not already indexed
    demo_dir = Path("data/demo_samples")
    if demo_dir.exists():
        for file_path in demo_dir.iterdir():
            if file_path.is_file():
                filename = file_path.name
                # Check if already in documents table
                cur.execute("SELECT id FROM documents WHERE filename = ?", (filename,))
                existing = cur.fetchone()
                if existing and existing[0] in chroma_doc_ids:
                    print(f"Document {filename} already indexed with ID {existing[0]}.")
                    continue
                
                print(f"Indexing demo file: {filename}...")
                doc_id = str(uuid.uuid4())
                with open(file_path, "rb") as f:
                    content_bytes = f.read()
                
                ext = file_path.suffix.lstrip(".").lower()
                pages, _ = extract_document_text(content_bytes, ext)
                
                # Index in Chroma + BM25
                IndexingService.index_document(
                    document_id=doc_id,
                    filename=filename,
                    pages=pages
                )
                
                # Copy file to uploads
                upload_target = settings.upload_path / f"{doc_id}{file_path.suffix}"
                with open(upload_target, "wb") as f:
                    f.write(content_bytes)
                
                # Insert record into SQLite documents table
                from datetime import datetime, timezone
                now_str = datetime.now(timezone.utc).isoformat()
                file_size = len(content_bytes)
                
                # Count indexed chunks
                chunks = vector_store.get_chunks_by_document(doc_id)
                chunk_count = len(chunks)
                
                import hashlib
                content_hash = hashlib.sha256(content_bytes).hexdigest()
                
                cur.execute(
                    """
                    INSERT INTO documents (id, filename, file_type, content_hash, status, chunk_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        filename,
                        ext,
                        content_hash,
                        "indexed",
                        chunk_count,
                        now_str,
                        now_str,
                    )
                )
                conn.commit()
                print(f"Successfully indexed {filename} (ID: {doc_id}, chunks: {chunk_count})")
                
    cur.execute("SELECT id, filename, chunk_count, status FROM documents")
    final_docs = cur.fetchall()
    print("\n--- Final Clean Indexed Documents Catalog ---")
    for d in final_docs:
        print(f"ID: {d[0]} | Filename: {d[1]} | Chunks: {d[2]} | Status: {d[3]}")
    conn.close()

if __name__ == "__main__":
    sync_and_seed()
