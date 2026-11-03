"""
Chat and grounded question-answering service with multi-turn conversation support.

Why: Coordinates the end-to-end RAG pipeline across retrieval, reranking, evidence sufficiency
evaluation, prompt generation, LLM completion, server-side citation validation, and session persistence.
Enforces unidirectional flow: Endpoints -> Service -> Retrieval/Reranker/Generation/Persistence.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Citation,
    RerankedPassage
)
from app.schemas.citation import SourcePanelItem
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import get_reranker, CrossEncoderReranker
from app.generation.provider import get_llm_provider, BaseLLMProvider
from app.generation.prompts import SYSTEM_GROUNDING_PROMPT, format_context_prompt
from app.services.citation_service import CitationService
from app.services.conversation_service import ConversationService

logger = logging.getLogger("nexusai.chat_service")

ABSTENTION_MESSAGE = "The available documents do not provide enough information to answer this question."


class ChatService:
    """
    Orchestrates the multi-stage grounded Q&A workflow with conversational state tracking.
    """

    @classmethod
    def answer_question(
        cls,
        request: ChatRequest,
        provider: Optional[BaseLLMProvider] = None
    ) -> ChatResponse:
        """
        Execute grounded Q&A over ingested documents.
        
        Args:
            request: ChatRequest with query, top_k, filters, reranking, and conversation_id.
            provider: Optional explicit LLM provider (useful for testing or overrides).
            
        Returns:
            ChatResponse with answer, validated citations, source panel, and execution telemetry.
        """
        overall_start = time.perf_counter()
        timings: Dict[str, float] = {}

        # -------------------------------------------------------------
        # Step 0: Conversation Session Tracking & History Resolution
        # -------------------------------------------------------------
        history = []
        retrieval_query = request.query

        if request.conversation_id:
            conv = ConversationService.get_conversation(request.conversation_id)
            if not conv:
                # If non-existent conversation_id passed, auto-create to be resilient
                ConversationService.create_conversation(title=request.query[:40])
            
            history = ConversationService.get_recent_history(request.conversation_id, limit=4)
            # Record user message in database
            ConversationService.add_message(
                conversation_id=request.conversation_id,
                role="user",
                content=request.query
            )

            # Query Contextualization: if query is short or uses referential terms, enrich with prior user turn
            if history and (len(request.query.split()) < 6 or any(w in request.query.lower().split() for w in ["it", "that", "this", "they", "them", "who"])):
                last_user_turns = [h[1] for h in history if h[0] == "user"]
                if last_user_turns:
                    retrieval_query = f"{last_user_turns[-1]} {request.query}"
                    logger.debug("Contextualized retrieval query: '%s'", retrieval_query)

        # -------------------------------------------------------------
        # Step 1: First-Stage Hybrid Retrieval (Vector + BM25 + RRF)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        hybrid_candidates = HybridRetriever.retrieve(
            query=retrieval_query,
            top_k=request.top_k,
            document_id=request.document_id,
            candidate_multiplier=request.candidate_multiplier,
            rrf_k=settings.RRF_K
        )
        timings["hybrid_retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        candidate_count = len(hybrid_candidates)

        # Immediate abstention if first-stage retrieval found zero documents
        if candidate_count == 0:
            timings["total_duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)
            if request.conversation_id:
                ConversationService.add_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=ABSTENTION_MESSAGE,
                    insufficient_evidence=True
                )
            return ChatResponse(
                answer=ABSTENTION_MESSAGE,
                citations=[],
                source_panel=[],
                insufficient_evidence=True,
                conversation_id=request.conversation_id,
                retrieval_metadata={
                    "retriever": "hybrid",
                    "candidate_count": 0,
                    "reranked_count": 0,
                    "timings": timings
                }
            )

        # -------------------------------------------------------------
        # Step 2: Second-Stage Passage Reranking (Cross-Encoder)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        if request.use_reranker:
            reranker = get_reranker()
            passages: List[RerankedPassage] = reranker.rerank(
                query=retrieval_query,
                candidates=hybrid_candidates,
                top_k=request.top_k
            )
        else:
            passages = CrossEncoderReranker.fallback_passthrough(
                candidates=hybrid_candidates,
                top_k=request.top_k
            )
        timings["reranking_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # -------------------------------------------------------------
        # Step 3: Evidence Sufficiency Gate
        # -------------------------------------------------------------
        if request.use_reranker and passages and passages[0].rerank_score < settings.EVIDENCE_MIN_SCORE:
            logger.info(
                "Abstaining: top passage score %.3f is below threshold %.3f",
                passages[0].rerank_score,
                settings.EVIDENCE_MIN_SCORE
            )
            timings["total_duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)
            if request.conversation_id:
                ConversationService.add_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=ABSTENTION_MESSAGE,
                    insufficient_evidence=True
                )
            return ChatResponse(
                answer=ABSTENTION_MESSAGE,
                citations=[],
                source_panel=[],
                insufficient_evidence=True,
                conversation_id=request.conversation_id,
                retrieval_metadata={
                    "retriever": "hybrid_cross_encoder",
                    "candidate_count": candidate_count,
                    "reranked_count": len(passages),
                    "top_score": passages[0].rerank_score,
                    "timings": timings
                }
            )

        # -------------------------------------------------------------
        # Step 4: Format Evidence-Grounded Prompt with Conversation History
        # -------------------------------------------------------------
        prompt = format_context_prompt(
            query=request.query,
            passages=passages,
            history=history
        )

        # -------------------------------------------------------------
        # Step 5: Execute LLM Completion via Provider Adapter
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        llm = provider or get_llm_provider()
        gen_result = llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_GROUNDING_PROMPT,
            temperature=0.0
        )
        timings["llm_generation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # -------------------------------------------------------------
        # Step 6: Server-Side Citation Validation & Source Panel Enrichment
        # -------------------------------------------------------------
        validated_citations, source_panel, discarded_ids = CitationService.validate_and_enrich(
            cited_chunk_ids=gen_result.cited_chunk_ids,
            retrieved_passages=passages,
            generated_answer=gen_result.text,
            insufficient_evidence=gen_result.insufficient_evidence
        )

        # -------------------------------------------------------------
        # Step 7: Persist Assistant Response in Session History
        # -------------------------------------------------------------
        if request.conversation_id:
            ConversationService.add_message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=gen_result.text,
                citations=source_panel,
                insufficient_evidence=gen_result.insufficient_evidence
            )

        timings["total_duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)

        return ChatResponse(
            answer=gen_result.text,
            citations=validated_citations,
            source_panel=source_panel,
            insufficient_evidence=gen_result.insufficient_evidence,
            conversation_id=request.conversation_id,
            retrieval_metadata={
                "retriever": "hybrid_cross_encoder" if request.use_reranker else "hybrid_rrf",
                "candidate_count": candidate_count,
                "reranked_count": len(passages),
                "model_name": gen_result.model_name,
                "discarded_citations": discarded_ids,
                "timings": timings
            }
        )
