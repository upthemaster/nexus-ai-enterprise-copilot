"""
Golden dataset loader and evaluation corpus seeder.

Why: Provides deterministic loading and schema validation of versioned golden datasets
and idempotent indexing of the reference enterprise evaluation corpus.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.schemas.evaluation import GoldenDatasetItem
from app.schemas.document import PageExtraction
from app.schemas.chunk import DocumentChunk
from app.ingestion.chunker import chunk_extracted_pages
from app.services.indexing_service import IndexingService

logger = logging.getLogger("nexusai.evaluation.dataset")

DATASETS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "datasets"
CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "corpus"


def get_dataset_path(version: str = "v1") -> Path:
    """
    Resolve the absolute filesystem path for a specific dataset version.
    """
    clean_version = version if version.endswith(".jsonl") else f"{version}.jsonl"
    path = DATASETS_DIR / clean_version
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset version '{version}' not found at: {path}")
    return path


def load_golden_dataset(version: str = "v1") -> List[GoldenDatasetItem]:
    """
    Load and validate a versioned golden evaluation dataset from JSONL format.
    """
    path = get_dataset_path(version)
    items: List[GoldenDatasetItem] = []
    
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw_data = json.loads(stripped)
                item = GoldenDatasetItem(**raw_data)
                items.append(item)
            except Exception as e:
                logger.error("Failed to parse golden dataset line %d in %s: %s", line_num, path, e)
                raise ValueError(f"Invalid dataset record at line {line_num}: {e}") from e

    logger.info("Successfully loaded %d golden dataset items from %s", len(items), path.name)
    return items


def seed_evaluation_corpus(corpus_dir: Optional[Path] = None) -> List[DocumentChunk]:
    """
    Index all reference text documents in the evaluation corpus into VectorStore and BM25Index
    via IndexingService. Idempotent: skips chunks that are already indexed in both engines.
    """
    target_dir = corpus_dir or CORPUS_DIR
    if not target_dir.exists():
        raise FileNotFoundError(f"Evaluation corpus directory not found at: {target_dir}")

    all_chunks: List[DocumentChunk] = []

    for file_path in sorted(target_dir.glob("*.txt")):
        document_id = file_path.stem
        filename = file_path.name
        text = file_path.read_text(encoding="utf-8")
        
        pages = [
            PageExtraction(
                page_number=1,
                text=text,
                character_count=len(text)
            )
        ]
        
        # Dual-index using IndexingService
        IndexingService.index_document(
            document_id=document_id,
            filename=filename,
            pages=pages
        )

        # Collect chunks for caller reference
        chunks = chunk_extracted_pages(
            document_id=document_id,
            filename=filename,
            pages=pages,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        all_chunks.extend(chunks)

    logger.info("Successfully seeded %d chunks across corpus files", len(all_chunks))
    return all_chunks
