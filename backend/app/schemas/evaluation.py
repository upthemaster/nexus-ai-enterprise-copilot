"""
Evaluation and benchmark data schemas.

Why: Enforces typed contracts for Golden Dataset items, evaluation runs,
ablation benchmarks, and quantitative information retrieval (IR) and RAG metrics.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """
    Curated question categories as specified in Master Blueprint Section 11.
    """
    DIRECT_FACTUAL = "direct_factual"
    ALPHANUMERIC_CODE = "alphanumeric_code"
    MULTI_HOP = "multi_hop"
    SUMMARIZATION = "summarization"
    NEGATIVE_ABSTENTION = "negative_abstention"


class RetrievalConfig(str, Enum):
    """
    Ablation benchmark retrieval configurations.
    """
    VECTOR_ONLY = "vector_only"
    BM25_ONLY = "bm25_only"
    HYBRID_RRF = "hybrid_rrf"
    HYBRID_RERANK = "hybrid_rerank"


class GoldenDatasetItem(BaseModel):
    """
    A single ground-truth test case in the evaluation dataset.
    """
    query_id: str = Field(description="Unique identifier for the evaluation query")
    query: str = Field(description="Natural language query or test prompt")
    question_type: QuestionType = Field(description="Question categorization")
    expected_answer: Optional[str] = Field(default=None, description="Reference ground-truth answer text or summary")
    ground_truth_chunk_ids: List[str] = Field(default_factory=list, description="List of relevant chunk IDs")
    ground_truth_doc_ids: List[str] = Field(default_factory=list, description="List of relevant document IDs")
    is_unanswerable: bool = Field(default=False, description="True if query cannot be answered from the corpus (requires abstention)")
    notes: Optional[str] = Field(default=None, description="Contextual evaluation notes")


class RetrievalMetrics(BaseModel):
    """
    Information retrieval metrics calculated over a top-K retrieved candidate list.
    """
    recall_at_1: float = Field(default=0.0, description="Proportion of relevant chunks in top 1")
    recall_at_3: float = Field(default=0.0, description="Proportion of relevant chunks in top 3")
    recall_at_5: float = Field(default=0.0, description="Proportion of relevant chunks in top 5")
    hit_at_1: float = Field(default=0.0, description="1.0 if at least one relevant chunk in top 1, else 0.0")
    hit_at_3: float = Field(default=0.0, description="1.0 if at least one relevant chunk in top 3, else 0.0")
    hit_at_5: float = Field(default=0.0, description="1.0 if at least one relevant chunk in top 5, else 0.0")
    mrr: float = Field(default=0.0, description="Mean Reciprocal Rank (1 / rank of first relevant chunk)")
    context_precision: float = Field(default=0.0, description="Mean Average Precision at K (MAP@K)")
    context_recall: float = Field(default=0.0, description="Fraction of all relevant chunks successfully retrieved")


class GenerationMetrics(BaseModel):
    """
    Grounded generation and verifiable citation metrics.
    """
    faithfulness: float = Field(default=0.0, description="Ratio of answer claims supported by retrieved context")
    citation_precision: float = Field(default=0.0, description="Ratio of cited chunks that are truly relevant")
    citation_recall: float = Field(default=0.0, description="Ratio of relevant ground-truth chunks cited")
    verbatim_quote_ratio: float = Field(default=0.0, description="Proportion of answer sentences matching verbatim quotes")
    abstention_accuracy: float = Field(default=0.0, description="1.0 if system correctly abstains on negative queries, else 0.0")


class OperationalMetrics(BaseModel):
    """
    System runtime and efficiency telemetry.
    """
    latency_p50_ms: float = Field(default=0.0, description="Median latency in milliseconds")
    latency_p90_ms: float = Field(default=0.0, description="90th percentile latency in milliseconds")
    latency_p95_ms: float = Field(default=0.0, description="95th percentile latency in milliseconds")
    latency_mean_ms: float = Field(default=0.0, description="Average latency in milliseconds")
    total_queries: int = Field(default=0, description="Number of evaluated queries")
    estimated_tokens_per_query: float = Field(default=0.0, description="Average estimated token usage per query")


class EvaluationItemResult(BaseModel):
    """
    Detailed evaluation output for a single dataset query.
    """
    query_id: str
    query: str
    question_type: QuestionType
    is_unanswerable: bool
    retrieved_chunk_ids: List[str]
    retrieved_ranks: Dict[str, int] = Field(default_factory=dict)
    retrieval_metrics: RetrievalMetrics
    generated_answer: Optional[str] = None
    cited_chunk_ids: List[str] = Field(default_factory=list)
    generation_metrics: Optional[GenerationMetrics] = None
    insufficient_evidence: bool = False
    latency_ms: float = 0.0
    passed: bool = True


class EvaluationRunRequest(BaseModel):
    """
    Request payload to execute an automated evaluation run.
    """
    dataset_version: str = Field(default="v1", description="Evaluation dataset version identifier")
    retrieval_config: RetrievalConfig = Field(default=RetrievalConfig.HYBRID_RERANK, description="Retriever pipeline to evaluate")
    include_generation: bool = Field(default=True, description="Whether to execute end-to-end generation and citation evaluation")
    top_k: int = Field(default=5, ge=1, le=20, description="Top K retrieval budget")


class EvaluationRunSummary(BaseModel):
    """
    Aggregated summary of an evaluation run.
    """
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dataset_version: str
    retrieval_config: RetrievalConfig
    total_queries: int
    overall_retrieval_metrics: RetrievalMetrics
    overall_generation_metrics: Optional[GenerationMetrics] = None
    operational_metrics: OperationalMetrics
    breakdown_by_type: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class EvaluationRunResponse(BaseModel):
    """
    Full evaluation report containing run summary and individual item breakdowns.
    """
    summary: EvaluationRunSummary
    item_results: List[EvaluationItemResult]


class AblationConfigResult(BaseModel):
    """
    Summary metrics for a specific retrieval architecture configuration.
    """
    config_name: str
    retrieval_metrics: RetrievalMetrics
    latency_mean_ms: float
    latency_p95_ms: float


class AblationComparisonResponse(BaseModel):
    """
    Comparative matrix across all 4 retrieval configurations.
    """
    dataset_version: str
    total_queries: int
    configurations: Dict[str, AblationConfigResult]
    best_performing_config: str
    key_findings: List[str]

