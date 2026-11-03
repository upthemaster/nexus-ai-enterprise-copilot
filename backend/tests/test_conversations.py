"""
Automated tests for conversation lifecycle and multi-turn session persistence (Day 5).

Why: Verifies Table 11 and Table 16 requirements:
- Conversations and messages persist in SQLite.
- Multi-turn context is stored and query history is accessible.
- Citation metadata and source panels are preserved across turns.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.session import init_db
from app.schemas.document import PageExtraction
from app.services.indexing_service import IndexingService


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """
    Ensure each test runs with an isolated temporary SQLite database and Chroma directory.
    """
    test_db = tmp_path / "test_conversations.db"
    test_chroma = tmp_path / "test_chroma"
    test_bm25 = tmp_path / "test_bm25.json"

    monkeypatch.setattr("app.core.config.settings.SQLITE_DB_PATH", str(test_db))
    monkeypatch.setattr("app.core.config.settings.CHROMA_PERSIST_DIR", str(test_chroma))
    monkeypatch.setattr("app.core.config.settings.BM25_PERSIST_PATH", str(test_bm25))

    init_db()


@pytest.mark.asyncio
async def test_conversation_crud_lifecycle():
    """
    Verifies full lifecycle: create, list, retrieve, and delete a conversation session.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create conversation
        create_resp = await client.post("/api/v1/conversations", json={"title": "HR Onboarding Chat"})
        assert create_resp.status_code == 201
        conv_data = create_resp.json()
        conv_id = conv_data["id"]
        assert conv_data["title"] == "HR Onboarding Chat"
        assert conv_data["message_count"] == 0

        # 2. List conversations
        list_resp = await client.get("/api/v1/conversations")
        assert list_resp.status_code == 200
        conversations = list_resp.json()
        assert any(c["id"] == conv_id for c in conversations)

        # 3. Retrieve conversation detail
        detail_resp = await client.get(f"/api/v1/conversations/{conv_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == conv_id
        assert detail["messages"] == []

        # 4. Delete conversation
        del_resp = await client.delete(f"/api/v1/conversations/{conv_id}")
        assert del_resp.status_code == 204

        # 5. Confirm deletion
        confirm_resp = await client.get(f"/api/v1/conversations/{conv_id}")
        assert confirm_resp.status_code == 404


@pytest.mark.asyncio
async def test_multi_turn_chat_session_persistence():
    """
    Verifies that POST /api/v1/chat persists user turns and assistant responses
    with full citation metadata across multiple conversational turns.
    """
    # Index test document
    doc_text = (
        "Travel & Expense Policy TEP-500. "
        "Employees must submit all expense receipts within thirty calendar days of travel. "
        "Late submissions will require special written authorization from the Division Vice President."
    )
    IndexingService.index_document(
        document_id="doc_tep_500",
        filename="travel_policy.pdf",
        pages=[PageExtraction(page_number=1, text=doc_text, character_count=len(doc_text))]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create conversation session
        conv_resp = await client.post("/api/v1/conversations", json={"title": "Expense Inquiries"})
        conv_id = conv_resp.json()["id"]

        # Turn 1: Initial query
        turn1_payload = {
            "query": "What is the deadline for submitting expense receipts under TEP-500?",
            "top_k": 2,
            "conversation_id": conv_id
        }
        turn1_resp = await client.post("/api/v1/chat", json=turn1_payload)
        assert turn1_resp.status_code == 200
        t1_data = turn1_resp.json()
        assert t1_data["conversation_id"] == conv_id
        assert t1_data["insufficient_evidence"] is False
        assert len(t1_data["citations"]) >= 1
        assert len(t1_data["source_panel"]) >= 1

        # Turn 2: Follow-up query leveraging context
        turn2_payload = {
            "query": "Who must authorize late submissions?",
            "top_k": 2,
            "conversation_id": conv_id
        }
        turn2_resp = await client.post("/api/v1/chat", json=turn2_payload)
        assert turn2_resp.status_code == 200
        t2_data = turn2_resp.json()
        assert t2_data["conversation_id"] == conv_id

        # Inspect persisted conversation detail from database
        history_resp = await client.get(f"/api/v1/conversations/{conv_id}")
        assert history_resp.status_code == 200
        history_data = history_resp.json()

        # Must contain 4 messages: (user, assistant, user, assistant)
        assert len(history_data["messages"]) == 4
        assert history_data["messages"][0]["role"] == "user"
        assert history_data["messages"][1]["role"] == "assistant"
        assert history_data["messages"][2]["role"] == "user"
        assert history_data["messages"][3]["role"] == "assistant"

        # Verify citations were persisted for assistant messages
        assert len(history_data["messages"][1]["citations"]) >= 1
        assert history_data["messages"][1]["citations"][0]["document_id"] == "doc_tep_500"


@pytest.mark.asyncio
async def test_conversation_not_found_returns_404():
    """
    Verifies that requesting an invalid conversation ID returns HTTP 404.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/conversations/non_existent_uuid_9999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

