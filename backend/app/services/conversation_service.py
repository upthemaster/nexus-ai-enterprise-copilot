"""
Conversation and session state management service.

Why: Manages multi-turn conversation lifecycle, SQLite persistence, and history retrieval
adhering to Blueprint Table 4, 11, and 16.
"""

import json
import logging
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import ConversationModel, MessageModel
from app.schemas.conversation import (
    ConversationRead,
    ConversationDetail,
    MessageRead
)
from app.schemas.citation import SourcePanelItem

logger = logging.getLogger("nexusai.conversation")


class ConversationService:
    """
    CRUD orchestration for conversations and message turns using SQLite.
    """

    @classmethod
    def create_conversation(
        cls,
        title: Optional[str] = None,
        db: Optional[Session] = None
    ) -> ConversationRead:
        """
        Create and persist a new conversation session.
        """
        session = db or SessionLocal()
        should_close = db is None

        try:
            conv = ConversationModel(
                title=title or f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            )
            session.add(conv)
            session.commit()
            session.refresh(conv)

            return ConversationRead(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=0
            )
        finally:
            if should_close:
                session.close()

    @classmethod
    def list_conversations(cls, db: Optional[Session] = None) -> List[ConversationRead]:
        """
        List all conversations ordered by most recent update.
        """
        session = db or SessionLocal()
        should_close = db is None

        try:
            convs = session.query(ConversationModel).order_by(ConversationModel.updated_at.desc()).all()
            results: List[ConversationRead] = []
            for c in convs:
                count = len(c.messages) if c.messages else 0
                results.append(
                    ConversationRead(
                        id=c.id,
                        title=c.title,
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                        message_count=count
                    )
                )
            return results
        finally:
            if should_close:
                session.close()

    @classmethod
    def get_conversation(
        cls,
        conversation_id: str,
        db: Optional[Session] = None
    ) -> Optional[ConversationDetail]:
        """
        Retrieve a conversation and its full chronological message history.
        """
        session = db or SessionLocal()
        should_close = db is None

        try:
            conv = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
            if not conv:
                return None

            messages: List[MessageRead] = []
            for m in conv.messages:
                citations: List[SourcePanelItem] = []
                if m.citations_json:
                    try:
                        raw_cites = json.loads(m.citations_json)
                        citations = [SourcePanelItem(**c) for c in raw_cites]
                    except Exception as e:
                        logger.warning("Failed to deserialize citations for message_id=%s: %s", m.id, e)

                messages.append(
                    MessageRead(
                        id=m.id,
                        role=m.role,
                        content=m.content,
                        citations=citations,
                        insufficient_evidence=m.insufficient_evidence,
                        created_at=m.created_at
                    )
                )

            return ConversationDetail(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                messages=messages
            )
        finally:
            if should_close:
                session.close()

    @classmethod
    def delete_conversation(cls, conversation_id: str, db: Optional[Session] = None) -> bool:
        """
        Delete a conversation and all cascaded messages.
        """
        session = db or SessionLocal()
        should_close = db is None

        try:
            conv = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
            if not conv:
                return False

            session.delete(conv)
            session.commit()
            return True
        finally:
            if should_close:
                session.close()

    @classmethod
    def add_message(
        cls,
        conversation_id: str,
        role: str,
        content: str,
        citations: Optional[List[SourcePanelItem]] = None,
        insufficient_evidence: bool = False,
        db: Optional[Session] = None
    ) -> MessageRead:
        """
        Persist a message turn to a conversation session and update conversation timestamp.
        """
        session = db or SessionLocal()
        should_close = db is None

        try:
            conv = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found.")

            citations_json = None
            if citations:
                citations_json = json.dumps([c.model_dump() for c in citations])

            msg = MessageModel(
                conversation_id=conversation_id,
                role=role,
                content=content,
                citations_json=citations_json,
                insufficient_evidence=insufficient_evidence
            )
            session.add(msg)
            conv.updated_at = datetime.utcnow()

            # Auto-title conversation from first user message if still default
            if role == "user" and conv.title.startswith("Chat 202"):
                short_title = content[:40].strip()
                if len(content) > 40:
                    short_title += "..."
                conv.title = short_title

            session.commit()
            session.refresh(msg)

            return MessageRead(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                citations=citations or [],
                insufficient_evidence=msg.insufficient_evidence,
                created_at=msg.created_at
            )
        finally:
            if should_close:
                session.close()

    @classmethod
    def get_recent_history(
        cls,
        conversation_id: str,
        limit: int = 4,
        db: Optional[Session] = None
    ) -> List[Tuple[str, str]]:
        """
        Retrieve recent (role, content) message pairs for prompt context formatting.
        """
        detail = cls.get_conversation(conversation_id, db=db)
        if not detail or not detail.messages:
            return []

        recent = detail.messages[-limit:]
        return [(m.role, m.content) for m in recent]

