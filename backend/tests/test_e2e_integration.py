"""
End-to-end integration test suite simulating a complete enterprise user session.

Why: Validates that all subsystems—Ingestion, Dual-Indexing, Hybrid RRF, Cross-Encoder
Reranking, Grounded Generation, Source Sidecar Inspector, LangGraph Workflow Orchestration,
and Relational Conversation Storage—operate cohesively in an end-to-end lifecycle.
"""

import pytest
import httpx


@pytest.mark.asyncio
async def test_full_enterprise_copilot_lifecycle(async_client: httpx.AsyncClient):
    """
    Simulates a full enterprise user journey from ingestion to multi-turn grounded chat,
    workflow execution, citation inspection, explicit abstention, and cleanup.
    """
    # -------------------------------------------------------------------------
    # 1. Health Check
    # -------------------------------------------------------------------------
    health_res = await async_client.get("/api/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # -------------------------------------------------------------------------
    # 2. Document Ingestion
    # -------------------------------------------------------------------------
    policy_text = (
        "POL-SRE-2026 mandates a 15-minute response SLA for Critical P1 incidents. "
        "High P2 incidents require a 1-hour response SLA. "
        "Cloud snapshots are captured every 4 hours for disaster recovery."
    )
    files = {"file": ("cloud_sla_policy.txt", policy_text.encode("utf-8"), "text/plain")}
    upload_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]
    assert upload_res.json()["chunk_count"] >= 1

    try:
        # ---------------------------------------------------------------------
        # 3. Document Catalog Listing & Details
        # ---------------------------------------------------------------------
        list_res = await async_client.get("/api/v1/documents")
        assert list_res.status_code == 200
        docs = list_res.json()["documents"]
        assert any(d["id"] == doc_id for d in docs)

        detail_res = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert detail_res.status_code == 200
        assert detail_res.json()["filename"] == "cloud_sla_policy.txt"

        # ---------------------------------------------------------------------
        # 4. Create Conversation Session
        # ---------------------------------------------------------------------
        conv_res = await async_client.post(
            "/api/v1/conversations",
            json={"title": "Cloud SLA Policy Review"}
        )
        assert conv_res.status_code in (200, 201)
        conv_id = conv_res.json()["id"]

        # ---------------------------------------------------------------------
        # 5. Grounded Q&A via LangGraph Workflow
        # ---------------------------------------------------------------------
        q1_payload = {
            "query": "What is the mandatory response SLA for Critical P1 cloud incidents under POL-SRE-2026?",
            "workflow_type": "qa",
            "conversation_id": conv_id,
            "top_k": 3
        }
        workflow_res1 = await async_client.post("/api/v1/workflows/run", json=q1_payload)
        assert workflow_res1.status_code == 200
        w1_data = workflow_res1.json()
        ans1 = w1_data.get("result", w1_data.get("answer", ""))

        assert "15-minute" in ans1 or "15" in ans1
        assert w1_data["insufficient_evidence"] is False
        assert len(w1_data["citations"]) >= 1
        assert "classify_query" in w1_data["execution_route"]
        assert "generate_qa" in w1_data["execution_route"]

        # ---------------------------------------------------------------------
        # 6. Click-to-Verify Source Citation Inspection
        # ---------------------------------------------------------------------
        first_citation = w1_data["citations"][0]
        chunk_id = first_citation["chunk_id"]

        source_res = await async_client.get(f"/api/v1/citations/{chunk_id}")
        assert source_res.status_code == 200
        source_data = source_res.json()
        assert source_data["chunk_id"] == chunk_id
        assert "Critical P1" in source_data["text"] or "POL-SRE-2026" in source_data["text"]

        # ---------------------------------------------------------------------
        # 7. Multi-Turn Follow-Up Query
        # ---------------------------------------------------------------------
        q2_payload = {
            "query": "What about P2 incidents?",
            "workflow_type": "qa",
            "conversation_id": conv_id,
            "top_k": 3
        }
        workflow_res2 = await async_client.post("/api/v1/workflows/run", json=q2_payload)
        assert workflow_res2.status_code == 200
        w2_data = workflow_res2.json()
        ans2 = w2_data.get("result", w2_data.get("answer", ""))
        assert "1-hour" in ans2 or "1 hour" in ans2 or "P2" in ans2 or "Critical" in ans2

        # ---------------------------------------------------------------------
        # 8. Document Summarization Workflow
        # ---------------------------------------------------------------------
        summary_res = await async_client.post(f"/api/v1/documents/{doc_id}/summarize")
        assert summary_res.status_code == 200
        s_data = summary_res.json()
        assert len(s_data["summary"]) > 0
        assert len(s_data["key_findings"]) >= 1
        assert len(s_data["citations"]) >= 1

        # ---------------------------------------------------------------------
        # 9. Document Risk Extraction Workflow
        # ---------------------------------------------------------------------
        risk_res = await async_client.post(f"/api/v1/documents/{doc_id}/risks")
        assert risk_res.status_code == 200
        r_data = risk_res.json()
        assert "overall_risk_level" in r_data

        # ---------------------------------------------------------------------
        # 10. Explicit Abstention on Out-of-Domain Query
        # ---------------------------------------------------------------------
        unanswerable_payload = {
            "query": "What is the corporate travel allowance for commercial flights to Mars?",
            "workflow_type": "qa",
            "conversation_id": conv_id,
            "top_k": 3
        }
        abstain_res = await async_client.post("/api/v1/workflows/run", json=unanswerable_payload)
        assert abstain_res.status_code == 200
        a_data = abstain_res.json()
        assert a_data["insufficient_evidence"] is True
        ans_abstain = a_data.get("result", a_data.get("answer", ""))
        assert "do not provide enough information" in ans_abstain

        # ---------------------------------------------------------------------
        # 11. Cleanup Conversation
        # ---------------------------------------------------------------------
        del_conv = await async_client.delete(f"/api/v1/conversations/{conv_id}")
        assert del_conv.status_code in (200, 204)

    finally:
        # Cleanup Document
        del_doc = await async_client.delete(f"/api/v1/documents/{doc_id}")
        assert del_doc.status_code == 200

