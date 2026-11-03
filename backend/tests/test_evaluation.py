"""
Automated test suite for Day 7: Evaluation Framework, Golden Dataset & Retrieval Ablation.

Why: Verifies dataset schema compliance, mathematical correctness of IR/RAG metrics,
4-way retrieval ablation execution, and HTTP evaluation API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.evaluation import (
    QuestionType,
    RetrievalConfig,
    GoldenDatasetItem,
    EvaluationRunRequest,
)
from app.evaluation.dataset import load_golden_dataset, seed_evaluation_corpus
from app.evaluation.metrics import (
    calculate_hit_at_k,
    calculate_recall_at_k,
    calculate_mrr,
    calculate_context_precision,
    calculate_context_recall,
    calculate_citation_precision,
    calculate_citation_recall,
    calculate_abstention_accuracy,
    calculate_faithfulness,
    calculate_verbatim_quote_ratio,
    calculate_percentiles,
    compute_retrieval_metrics,
)
from app.evaluation.benchmarks import BenchmarkRunner
from app.services.evaluation_service import EvaluationService
from app.retrieval.bm25_index import get_bm25_manager
from app.retrieval.vector_store import get_vector_store


client = TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Golden Dataset Schema & Question Category Distribution
# ---------------------------------------------------------------------------

def test_golden_dataset_schema_and_distribution():
    """
    Verify that the v1 golden dataset loads cleanly and adheres to the 5 categories
    mandated in Master Blueprint Section 11.
    """
    items = load_golden_dataset("v1")
    assert len(items) == 25, f"Expected 25 golden items, got {len(items)}"

    counts = {}
    for item in items:
        assert item.query_id.startswith("q")
        assert len(item.query.strip()) > 10
        counts[item.question_type] = counts.get(item.question_type, 0) + 1

        if item.is_unanswerable:
            assert item.question_type == QuestionType.NEGATIVE_ABSTENTION
            assert len(item.ground_truth_chunk_ids) == 0
        else:
            assert len(item.ground_truth_chunk_ids) >= 1
            assert len(item.ground_truth_doc_ids) >= 1

    assert counts[QuestionType.DIRECT_FACTUAL] == 6
    assert counts[QuestionType.ALPHANUMERIC_CODE] == 5
    assert counts[QuestionType.MULTI_HOP] == 5
    assert counts[QuestionType.SUMMARIZATION] == 4
    assert counts[QuestionType.NEGATIVE_ABSTENTION] == 5


# ---------------------------------------------------------------------------
# Test 2: Pure Mathematical Information Retrieval Metrics
# ---------------------------------------------------------------------------

def test_retrieval_metrics_pure_math():
    """
    Verify exact mathematical behavior of Recall@K, Hit@K, MRR, Context Precision (MAP@K).
    """
    ground_truth = ["chunk_A", "chunk_B"]

    # Case 1: First item is relevant (rank 1)
    retrieved_1 = ["chunk_A", "chunk_X", "chunk_Y", "chunk_Z", "chunk_W"]
    assert calculate_hit_at_k(retrieved_1, ground_truth, 1) == 1.0
    assert calculate_recall_at_k(retrieved_1, ground_truth, 1) == 0.5
    assert calculate_recall_at_k(retrieved_1, ground_truth, 5) == 0.5
    assert calculate_mrr(retrieved_1, ground_truth) == 1.0

    # Case 2: Relevant item at rank 2
    retrieved_2 = ["chunk_X", "chunk_A", "chunk_Y"]
    assert calculate_hit_at_k(retrieved_2, ground_truth, 1) == 0.0
    assert calculate_hit_at_k(retrieved_2, ground_truth, 2) == 1.0
    assert calculate_mrr(retrieved_2, ground_truth) == 0.5

    # Case 3: Both relevant items retrieved at rank 1 and rank 2 (Perfect Context Precision)
    retrieved_perfect = ["chunk_A", "chunk_B", "chunk_X"]
    assert calculate_recall_at_k(retrieved_perfect, ground_truth, 2) == 1.0
    assert calculate_mrr(retrieved_perfect, ground_truth) == 1.0
    assert calculate_context_precision(retrieved_perfect, ground_truth, 3) == 1.0

    # Case 4: Relevant item at rank 3 (MAP@K penalty)
    retrieved_3 = ["chunk_X", "chunk_Y", "chunk_A"]
    # AP@3: i=3 hit -> precision at 3 = 1/3, denominator = min(len(ground_truth), 3) = 2 -> MAP = (1/3)/2 = 0.1667
    assert calculate_context_precision(retrieved_3, ground_truth, 3) == 0.1667

    # Case 5: Empty or unanswerable
    assert calculate_hit_at_k([], ground_truth, 3) == 0.0
    assert calculate_mrr([], ground_truth) == 0.0
    assert calculate_context_precision([], ground_truth, 3) == 0.0


# ---------------------------------------------------------------------------
# Test 3: Pure Mathematical Generation & Citation Metrics
# ---------------------------------------------------------------------------

def test_generation_and_citation_metrics_math():
    """
    Verify calculation of Citation Precision, Citation Recall, Abstention Accuracy, and percentiles.
    """
    gt_chunks = ["c1", "c2"]

    # Perfect citations
    assert calculate_citation_precision(["c1", "c2"], gt_chunks) == 1.0
    assert calculate_citation_recall(["c1", "c2"], gt_chunks) == 1.0

    # Hallucinated citation included (c3)
    assert calculate_citation_precision(["c1", "c3"], gt_chunks) == 0.5
    assert calculate_citation_recall(["c1", "c3"], gt_chunks) == 0.5

    # Abstention accuracy
    assert calculate_abstention_accuracy(is_unanswerable=True, insufficient_evidence=True) == 1.0
    assert calculate_abstention_accuracy(is_unanswerable=True, insufficient_evidence=False) == 0.0
    assert calculate_abstention_accuracy(is_unanswerable=False, insufficient_evidence=False) == 1.0
    assert calculate_abstention_accuracy(is_unanswerable=False, insufficient_evidence=True) == 0.0

    # Percentiles
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    p_stats = calculate_percentiles(latencies)
    assert p_stats["mean"] == 30.0
    assert p_stats["p50"] == 30.0
    assert p_stats["p90"] == 46.0
    assert p_stats["p95"] == 48.0


# ---------------------------------------------------------------------------
# Test 4: Evaluation Corpus Seeding
# ---------------------------------------------------------------------------

def test_evaluation_corpus_seeding():
    """
    Verify that reference corpus text files are chunked and indexed into VectorStore and BM25.
    """
    chunks = seed_evaluation_corpus()
    assert len(chunks) >= 15

    bm25 = get_bm25_manager()
    assert bm25.count() >= 15
    assert any("eval_sec_policy" in c.chunk_id for c in bm25._chunks)
    assert any("eval_cloud_infra" in c.chunk_id for c in bm25._chunks)


# ---------------------------------------------------------------------------
# Test 5: 4-Way Retrieval Ablation Runner
# ---------------------------------------------------------------------------

def test_retrieval_ablation_4_way_runner():
    """
    Verify that BenchmarkRunner executes all 4 retrieval configurations
    (Vector-only, BM25-only, Hybrid RRF, Hybrid + Reranker) and returns comparative metrics.
    """
    seed_evaluation_corpus()
    items = load_golden_dataset("v1")
    # Run ablation on first 5 representative items for rapid test execution
    subset = items[:5]

    ablation_resp = BenchmarkRunner.run_ablation_comparison(
        items=subset,
        top_k=3,
        dataset_version="v1"
    )

    assert ablation_resp.total_queries == 5
    assert "vector_only" in ablation_resp.configurations
    assert "bm25_only" in ablation_resp.configurations
    assert "hybrid_rrf" in ablation_resp.configurations
    assert "hybrid_rerank" in ablation_resp.configurations

    # Verify every config has valid retrieval metrics and timings
    for config_name, res in ablation_resp.configurations.items():
        assert res.retrieval_metrics.hit_at_3 >= 0.0
        assert res.retrieval_metrics.mrr >= 0.0
        assert res.latency_mean_ms >= 0.0

    assert len(ablation_resp.key_findings) == 4


# ---------------------------------------------------------------------------
# Test 6: End-to-End Evaluation Run with Grounded Generation
# ---------------------------------------------------------------------------

def test_end_to_end_evaluation_run_with_generation():
    """
    Verify end-to-end evaluation run executing retrieval, generation, citation validation,
    and abstention tracking across factual and unanswerable queries.
    """
    seed_evaluation_corpus()
    items = load_golden_dataset("v1")

    # Select 1 factual query and 1 unanswerable query
    test_items = [
        items[0],   # q01: PTO carryover (factual)
        items[20],  # q21: travel reimbursement (unanswerable negative)
    ]

    response = BenchmarkRunner.run_evaluation(
        items=test_items,
        config=RetrievalConfig.HYBRID_RERANK,
        include_generation=True,
        top_k=3,
        dataset_version="v1"
    )

    summary = response.summary
    assert summary.total_queries == 2
    assert summary.overall_retrieval_metrics is not None
    assert summary.overall_generation_metrics is not None

    # Verify individual results
    factual_res = response.item_results[0]
    negative_res = response.item_results[1]

    assert factual_res.is_unanswerable is False
    assert factual_res.retrieval_metrics.hit_at_3 == 1.0

    assert negative_res.is_unanswerable is True
    assert negative_res.insufficient_evidence is True
    assert negative_res.generation_metrics.abstention_accuracy == 1.0


# ---------------------------------------------------------------------------
# Test 7: Evaluation API Endpoints
# ---------------------------------------------------------------------------

def test_api_evaluation_endpoints():
    """
    Verify HTTP endpoints: POST /api/v1/evaluation/run, GET /ablation, GET /runs, GET /runs/{id}.
    """
    seed_evaluation_corpus()

    # 1. Trigger evaluation run via API (retrieval only for speed)
    req_body = {
        "dataset_version": "v1",
        "retrieval_config": "hybrid_rrf",
        "include_generation": False,
        "top_k": 3
    }
    run_res = client.post("/api/v1/evaluation/run", json=req_body)
    assert run_res.status_code == 200, run_res.text
    run_data = run_res.json()
    run_id = run_data["summary"]["run_id"]
    assert run_data["summary"]["total_queries"] == 25
    assert len(run_data["item_results"]) == 25

    # 2. List evaluation runs
    list_res = client.get("/api/v1/evaluation/runs")
    assert list_res.status_code == 200
    runs_list = list_res.json()
    assert len(runs_list) >= 1
    assert any(r["run_id"] == run_id for r in runs_list)

    # 3. Get single run details
    detail_res = client.get(f"/api/v1/evaluation/runs/{run_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["summary"]["run_id"] == run_id

    # 4. Get non-existent run returns 404
    missing_res = client.get("/api/v1/evaluation/runs/non_existent_run_999")
    assert missing_res.status_code == 404

    # 5. Run ablation benchmark endpoint
    ablation_res = client.get("/api/v1/evaluation/ablation?dataset_version=v1&top_k=3")
    assert ablation_res.status_code == 200
    ablation_data = ablation_res.json()
    assert "configurations" in ablation_data
    assert "hybrid_rerank" in ablation_data["configurations"]
