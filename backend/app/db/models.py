"""
SQLAlchemy ORM models for conversation sessions and message history.

Why: Adheres to Blueprint Table 11:
- Conversation: id, created_at, title
- Message: id, conversation_id, role, content, created_at, citations_json
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class DocumentModel(Base):
    """
    Persistent document record in relational storage.
    
    Why: Adheres to Blueprint Table 11:
    - Document: id, filename, file_type, content_hash, status, created_at, chunk_count, error_message
    """
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="indexed")  # "indexing", "indexed", "failed"
    chunk_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ConversationModel(Base):
    """
    Persistent conversational session record.
    """
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship(
        "MessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageModel.created_at"
    )


class MessageModel(Base):
    """
    Individual turn within a conversational session.
    """
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True)  # Serialized JSON list of citations
    insufficient_evidence = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("ConversationModel", back_populates="messages")

