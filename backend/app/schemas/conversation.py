"""
Pydantic schemas for conversation management and session history.

Why: Table 11 of the Master Blueprint specifies schema requirements for
Conversation (id, created_at, title) and Message (id, conversation_id, role, content, citations).
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.citation import SourcePanelItem


class MessageRead(BaseModel):
    """
    Individual turn within a conversation session.
    """
    id: str = Field(description="Message UUID")
    role: str = Field(description="Speaker role: user or assistant")
    content: str = Field(description="Text body of the message")
    citations: List[SourcePanelItem] = Field(default_factory=list, description="Verified source citations")
    insufficient_evidence: bool = Field(default=False, description="Whether the answer was an abstention")
    created_at: datetime = Field(description="Creation timestamp")


class ConversationCreate(BaseModel):
    """
    Payload to initialize a new conversation session.
    """
    title: Optional[str] = Field(default=None, max_length=255, description="Optional custom title for the conversation")


class ConversationRead(BaseModel):
    """
    Summary view of a conversation for list displays.
    """
    id: str = Field(description="Conversation UUID")
    title: str = Field(description="Display title of the conversation")
    created_at: datetime = Field(description="Timestamp when conversation was started")
    updated_at: datetime = Field(description="Timestamp of most recent activity")
    message_count: int = Field(default=0, description="Total number of messages in session")


class ConversationDetail(BaseModel):
    """
    Full conversation session with complete message history.
    """
    id: str = Field(description="Conversation UUID")
    title: str = Field(description="Display title of the conversation")
    created_at: datetime = Field(description="Timestamp when conversation was started")
    updated_at: datetime = Field(description="Timestamp of most recent activity")
    messages: List[MessageRead] = Field(default_factory=list, description="Chronological message history")

