"""
Conversation lifecycle API endpoints.

Why: Exposes CRUD endpoints for multi-turn conversational sessions and dialogue history,
adhering to Blueprint Table 10 and Table 11.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationDetail
)
from app.services.conversation_service import ConversationService

logger = logging.getLogger("nexusai.api.conversations")

router = APIRouter()


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation session",
    description="Initializes an empty conversational session in the relational SQLite database."
)
async def create_conversation(payload: ConversationCreate = ConversationCreate()) -> ConversationRead:
    """
    Initialize a new conversation.
    """
    try:
        return ConversationService.create_conversation(title=payload.title)
    except Exception as e:
        logger.error("Failed to create conversation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize conversation session."
        )


@router.get(
    "",
    response_model=List[ConversationRead],
    status_code=status.HTTP_200_OK,
    summary="List all conversations",
    description="Returns all conversation sessions ordered by most recent activity."
)
async def list_conversations() -> List[ConversationRead]:
    """
    List conversation sessions.
    """
    try:
        return ConversationService.list_conversations()
    except Exception as e:
        logger.error("Failed to list conversations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations."
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail and message history",
    description="Retrieves a conversation and all chronological message turns with validated citations."
)
async def get_conversation(conversation_id: str) -> ConversationDetail:
    """
    Get full conversation history.
    """
    conv = ConversationService.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    return conv


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    description="Deletes a conversation session and all associated messages."
)
async def delete_conversation(conversation_id: str) -> None:
    """
    Delete a conversation session.
    """
    deleted = ConversationService.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )

