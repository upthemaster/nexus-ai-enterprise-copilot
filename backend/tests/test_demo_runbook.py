"""
Automated validation test for Day 10 Comprehensive Demonstration Runbook.

Why: Programmatically executes all 7 scripted demonstration scenarios defined in
docs/DEMO_RUNBOOK.md to ensure that instructions and API behaviors remain 100%
reproducible and verified against regressions.
"""

import pytest
import httpx
from pathlib import Path


@pytest.mark.asyncio
async def test_complete_demo_runbook_scenarios(async_client: httpx.AsyncClient):
    """
    Execute all 7 demonstration runbook scenarios sequentially.
    """
    # -------------------------------------------------------------------------
    # Scenario 1: Multi-Format Document Ingestion & Catalog Verification
    # -------------------------------------------------------------------------
    demo_dir = Path("data/demo_samples")
    assert demo_dir.exists(), "data/demo_samples directory must exist"

    uploaded_doc_ids = []
    sample_files = [
        ("cloud_infrastructure_sla.txt", "text/plain"),
        ("enterprise_security_travel_policy.pdf", "application/pdf"),
        ("vendor_master_services_agreement.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]

    for fname, mime in sample_files:
        fpath = demo_dir / fname
        assert fpath.exists(), f"Sample file {fname} must exist"
        with open(fpath, "rb") as f:
            b = f.read()

        up_resp = await async_client.post(
            "/api/v1/documents/upload",
            files={"file": (fname, b, mime)}
        )
        assert up_resp.status_code == 200, f"Failed uploading {fname}: {up_resp.text}"
        doc_data = up_resp.json()
        assert "document_id" in doc_data
        assert doc_data["status"] in ("processed", "indexed")
        uploaded_doc_ids.append(doc_data["document_id"])

    # Verify documents appear in catalog
    cat_resp = await async_client.get("/api/v1/documents")
    assert cat_resp.status_code == 200
    catalog = cat_resp.json()["documents"]
    cat_names = [d["filename"] for d in catalog]
    for fname, _ in sample_files:
        assert fname in cat_names

    # -------------------------------------------------------------------------
    # Scenario 2: Grounded Q&A with Click-to-Verify Citation Sidecar
    # -------------------------------------------------------------------------
    qa_resp = await async_client.post(
        "/api/v1/chat",
        json={
            "query": "What is the capital expense approval limit under financial procedure PROC-889?",
            "top_k": 3
        }
    )
    assert qa_resp.status_code == 200
    qa_data = qa_resp.json()
    assert qa_data["insufficient_evidence"] is False
    assert len(qa_data["citations"]) >= 1

    # Verify citation sidecar inspectability
    cit = qa_data["citations"][0]
    chunk_id = cit["chunk_id"]
    sidecar_resp = await async_client.get(f"/api/v1/citations/{chunk_id}")
    assert sidecar_resp.status_code == 200
    sidecar_data = sidecar_resp.json()
    assert sidecar_data["chunk_id"] == chunk_id
    assert len(sidecar_data.get("text", sidecar_data.get("content", ""))) > 0

    # -------------------------------------------------------------------------
    # Scenario 3: Contextual Multi-Turn Conversation
    # -------------------------------------------------------------------------
    conv_create = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Cloud SLA & Escalation Inquiry"}
    )
    assert conv_create.status_code in (200, 201)
    conv_id = conv_create.json()["id"]

    turn1 = await async_client.post(
        "/api/v1/chat",
        json={
            "conversation_id": conv_id,
            "query": "What are the response time SLAs for cloud services?"
        }
    )
    assert turn1.status_code == 200

    turn2 = await async_client.post(
        "/api/v1/chat",
        json={
            "conversation_id": conv_id,
            "query": "What is the response window specifically for P1 critical outages and what happens if it is missed?"
        }
    )
    assert turn2.status_code == 200
    t2_data = turn2.json()
    assert t2_data["insufficient_evidence"] is False

    # -------------------------------------------------------------------------
    # Scenario 4: Executive Summarization Workflow
    # -------------------------------------------------------------------------
    msa_doc_id = uploaded_doc_ids[2]  # vendor_master_services_agreement.docx
    sum_resp = await async_client.post(f"/api/v1/documents/{msa_doc_id}/summarize")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["document_id"] == msa_doc_id
    assert len(sum_data["summary"]) > 0

    # -------------------------------------------------------------------------
    # Scenario 5: Structured Risk & Liability Extraction Workflow
    # -------------------------------------------------------------------------
    risk_resp = await async_client.post(f"/api/v1/documents/{msa_doc_id}/risks")
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["document_id"] == msa_doc_id
    assert len(risk_data["risks"]) > 0
    assert risk_data["overall_risk_level"] in ("HIGH", "MEDIUM", "LOW")

    # -------------------------------------------------------------------------
    # Scenario 6: Negative Abstention Gate (Zero Hallucination Verification)
    # -------------------------------------------------------------------------
    abs_resp = await async_client.post(
        "/api/v1/chat",
        json={
            "query": "What is the corporate policy regarding employee stock option vesting schedules and equity grants?",
            "top_k": 3
        }
    )
    assert abs_resp.status_code == 200
    abs_data = abs_resp.json()
    assert abs_data["insufficient_evidence"] is True
    ans_lower = abs_data["answer"].lower()
    assert "not provide enough information" in ans_lower or "sufficient information" in ans_lower

    # -------------------------------------------------------------------------
    # Scenario 7: Live 4-Way Retrieval Ablation Benchmark Execution
    # -------------------------------------------------------------------------
    ablation_resp = await async_client.get("/api/v1/evaluation/ablation")
    assert ablation_resp.status_code == 200
    ablation_data = ablation_resp.json()
    assert "configurations" in ablation_data
    configs = ablation_data["configurations"]
    assert "vector_only" in configs
    assert "bm25_only" in configs
    assert "hybrid_rrf" in configs
    assert "hybrid_rerank" in configs

    # Cleanup created conversation
    del_conv = await async_client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_conv.status_code in (200, 204)
