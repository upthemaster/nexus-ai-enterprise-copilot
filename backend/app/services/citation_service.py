"""
Citation validation and source inspection service.

Why: Section 6.6 and Table 8 of the Master Blueprint require:
- Rejecting citation IDs not present in retrieved context (anti-fabrication).
- Distinguishing direct quotations from paraphrases.
- Packaging rich SourcePanelItem data for UI inspection.
"""

import re
import logging
from typing import List, Optional, Tuple

from app.schemas.chat import RerankedPassage, Citation
from app.schemas.citation import (
    SourcePanelItem,
    SourceInspectorResponse,
    CitationValidationResult
)
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25_index import get_bm25_manager

logger = logging.getLogger("nexusai.citations")


class CitationService:
    """
    Coordinates server-side citation validation, verbatim quotation detection,
    and source chunk inspection.
    """

    @classmethod
    def validate_and_enrich(
        cls,
        cited_chunk_ids: List[str],
        retrieved_passages: List[RerankedPassage],
        generated_answer: str,
        insufficient_evidence: bool = False
    ) -> Tuple[List[Citation], List[SourcePanelItem], List[str]]:
        """
        Validate cited chunk IDs against retrieved passages, detect verbatim quotes,
        and construct both concise Citation and detailed SourcePanelItem models.
        
        Args:
            cited_chunk_ids: Chunk IDs referenced in the model's raw text.
            retrieved_passages: The actual passages provided in the prompt context.
            generated_answer: The final synthesized answer text.
            insufficient_evidence: Whether the generation was an abstention.
            
        Returns:
            Tuple of (List[Citation], List[SourcePanelItem], List[str] of discarded IDs).
        """
        if insufficient_evidence or not retrieved_passages:
            return [], [], []

        passage_map = {p.chunk_id: p for p in retrieved_passages}
        valid_citations: List[Citation] = []
        source_panel: List[SourcePanelItem] = []
        discarded_ids: List[str] = []

        # Step 1: Validate each cited chunk ID against retrieved passages
        target_chunk_ids: List[str] = []
        for cid in cited_chunk_ids:
            if cid in passage_map:
                if cid not in target_chunk_ids:
                    target_chunk_ids.append(cid)
            else:
                logger.warning("Discarded unsupplied/fabricated citation ID: %s", cid)
                discarded_ids.append(cid)

        # Fallback: If model answered affirmatively without bracket tags, cite the primary chunk
        if not target_chunk_ids and retrieved_passages:
            target_chunk_ids.append(retrieved_passages[0].chunk_id)

        # Step 2: Enrich citations with direct quotation analysis
        for idx, cid in enumerate(target_chunk_ids, start=1):
            passage = passage_map[cid]
            is_quote, quote_span = cls.detect_direct_quote(generated_answer, passage.text)

            snippet_text = passage.text[:160].strip()
            if len(passage.text) > 160:
                snippet_text += "..."

            # Standard citation
            citation = Citation(
                citation_index=idx,
                document_id=passage.document_id,
                filename=passage.filename,
                page_number=passage.page_number,
                chunk_id=passage.chunk_id,
                snippet=snippet_text,
                relevance_score=round(passage.rerank_score, 4),
                is_direct_quote=is_quote,
                quote_span=quote_span
            )
            valid_citations.append(citation)

            # Detailed source panel item
            panel_item = SourcePanelItem(
                citation_index=idx,
                document_id=passage.document_id,
                filename=passage.filename,
                page_number=passage.page_number,
                chunk_id=passage.chunk_id,
                snippet=passage.text,
                relevance_score=round(passage.rerank_score, 4),
                is_direct_quote=is_quote,
                quote_span=quote_span
            )
            source_panel.append(panel_item)

        return valid_citations, source_panel, discarded_ids

    @classmethod
    def validate_citations(
        cls,
        response_text: str,
        retrieved_passages: List[RerankedPassage],
        insufficient_evidence: bool = False
    ) -> List[Citation]:
        """
        Convenience validator extracting citations from response_text and enriching with passage metadata.
        """
        from app.generation.provider import BaseLLMProvider
        cited_ids = BaseLLMProvider.extract_chunk_citations(response_text)
        valid_citations, _, _ = cls.validate_and_enrich(
            cited_chunk_ids=cited_ids,
            retrieved_passages=retrieved_passages,
            generated_answer=response_text,
            insufficient_evidence=insufficient_evidence
        )
        return valid_citations

    @staticmethod
    def detect_direct_quote(answer: str, passage_text: str, min_chars: int = 20) -> Tuple[bool, Optional[str]]:
        """
        Check if the generated answer contains a verbatim quotation from the passage.
        
        Args:
            answer: Generated response.
            passage_text: Source passage text.
            min_chars: Minimum character length of a verbatim span to qualify as a quote.
            
        Returns:
            Tuple of (is_direct_quote: bool, quote_span: Optional[str]).
        """
        norm_answer = " ".join(answer.lower().split())

        # Search from largest word window down to 4 words
        words = passage_text.split()
        for window_size in range(len(words), 3, -1):
            for i in range(len(words) - window_size + 1):
                window = " ".join(words[i:i + window_size])
                if len(window) >= min_chars and window.lower() in norm_answer:
                    return True, window

        return False, None

    @classmethod
    def get_source_chunk(cls, chunk_id: str) -> Optional[SourceInspectorResponse]:
        """
        Retrieve complete passage content and metadata for UI inspection.
        """
        # Primary lookup: ChromaDB vector store
        vector_store = get_vector_store()
        chunk_item = vector_store.get_chunk_by_id(chunk_id)

        if chunk_item:
            return SourceInspectorResponse(
                chunk_id=chunk_item.chunk_id,
                document_id=chunk_item.document_id,
                filename=chunk_item.filename,
                page_number=chunk_item.page_number,
                chunk_index=chunk_item.chunk_index,
                text=chunk_item.text,
                character_count=len(chunk_item.text)
            )

        # Fallback lookup: BM25 index
        bm25_mgr = get_bm25_manager()
        bm25_item = bm25_mgr.get_chunk_by_id(chunk_id)
        if bm25_item:
            return SourceInspectorResponse(
                chunk_id=bm25_item.chunk_id,
                document_id=bm25_item.metadata.document_id,
                filename=bm25_item.metadata.filename,
                page_number=bm25_item.metadata.page_number,
                chunk_index=bm25_item.metadata.chunk_index,
                text=bm25_item.text,
                character_count=len(bm25_item.text)
            )

        return None
