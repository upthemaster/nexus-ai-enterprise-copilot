"""
Chat and question-answering API endpoint.

Why: Exposes POST /api/v1/chat for grounded Q&A over indexed documents, adhering to
Section 6.6, Table 10, and Section 18 of the Master Blueprint.
"""

import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

logger = logging.getLogger("nexusai.api.chat")

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question against indexed enterprise documents",
    description="Executes hybrid retrieval, cross-encoder reranking, evidence sufficiency check, and evidence-grounded generation."
)
async def ask_question(request: ChatRequest) -> ChatResponse:
    """
    Handle grounded question answering requests.
    """
    try:
        response = ChatService.answer_question(request)
        return response
    except Exception as e:
        logger.error("Error processing chat question: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating an answer. Please try again."
        )

