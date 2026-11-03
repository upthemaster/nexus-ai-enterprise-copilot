"""
Mathematical and algorithmic evaluation metrics engine for Information Retrieval (IR) and RAG generation.

Why: Provides deterministic, transparent, and reproducible metric calculators for
Recall@K, Hit@K, MRR, Context Precision (MAP@K), Faithfulness, Citation Precision/Recall,
Verbatim Quote Ratio, Abstention Accuracy, and Latency percentiles without relying on
opaque or non-deterministic third-party APIs.
"""

import math
import re
from typing import List, Dict, Set, Any, Optional

from app.schemas.evaluation import RetrievalMetrics, GenerationMetrics, OperationalMetrics
from app.services.citation_service import CitationService


# ---------------------------------------------------------------------------
# Retrieval Metrics
# ---------------------------------------------------------------------------

def calculate_hit_at_k(retrieved_ids: List[str], ground_truth_ids: List[str], k: int) -> float:
    """
    Compute binary Hit@K: 1.0 if at least one relevant ground-truth chunk appears in top-K.
    """
    if not ground_truth_ids:
        return 0.0
    gt_set = set(ground_truth_ids)
    for cid in retrieved_ids[:k]:
        if cid in gt_set:
            return 1.0
    return 0.0


def calculate_recall_at_k(retrieved_ids: List[str], ground_truth_ids: List[str], k: int) -> float:
    """
    Compute proportional Recall@K: fraction of total ground-truth chunks retrieved in top-K.
    """
    if not ground_truth_ids:
        return 0.0
    gt_set = set(ground_truth_ids)
    retrieved_k = set(retrieved_ids[:k])
    hits = len(retrieved_k & gt_set)
    return round(hits / len(gt_set), 4)


def calculate_mrr(retrieved_ids: List[str], ground_truth_ids: List[str]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR): 1 / rank of first relevant chunk.
    """
    if not ground_truth_ids:
        return 0.0
    gt_set = set(ground_truth_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in gt_set:
            return round(1.0 / rank, 4)
    return 0.0


def calculate_context_precision(retrieved_ids: List[str], ground_truth_ids: List[str], k: int = 5) -> float:
    """
    Compute Mean Average Precision at K (MAP@K) as Context Precision.
    Penalizes systems where relevant documents appear lower in the ranked list.
    """
    if not ground_truth_ids or not retrieved_ids:
        return 0.0
    
    gt_set = set(ground_truth_ids)
    max_k = min(k, len(retrieved_ids))
    denominator = min(len(gt_set), k)
    if denominator == 0:
        return 0.0

    cumulative_hits = 0
    sum_precisions = 0.0

    for i in range(1, max_k + 1):
        cid = retrieved_ids[i - 1]
        if cid in gt_set:
            cumulative_hits += 1
            precision_at_i = cumulative_hits / i
            sum_precisions += precision_at_i

    return round(sum_precisions / denominator, 4)


def calculate_context_recall(retrieved_ids: List[str], ground_truth_ids: List[str]) -> float:
    """
    Compute Context Recall across all retrieved candidates: |Retrieved ∩ Relevant| / |Relevant|.
    """
    if not ground_truth_ids:
        return 0.0
    gt_set = set(ground_truth_ids)
    hits = len(set(retrieved_ids) & gt_set)
    return round(hits / len(gt_set), 4)


def compute_retrieval_metrics(
    retrieved_ids: List[str],
    ground_truth_ids: List[str],
    is_unanswerable: bool = False
) -> RetrievalMetrics:
    """
    Compute the complete suite of retrieval metrics for a single query.
    """
    if is_unanswerable or not ground_truth_ids:
        # Negative / unanswerable query: no ground truth passages exist
        return RetrievalMetrics(
            recall_at_1=1.0 if not retrieved_ids else 0.0,
            recall_at_3=1.0 if not retrieved_ids else 0.0,
            recall_at_5=1.0 if not retrieved_ids else 0.0,
            hit_at_1=0.0,
            hit_at_3=0.0,
            hit_at_5=0.0,
            mrr=0.0,
            context_precision=0.0,
            context_recall=1.0 if not retrieved_ids else 0.0,
        )

    return RetrievalMetrics(
        recall_at_1=calculate_recall_at_k(retrieved_ids, ground_truth_ids, 1),
        recall_at_3=calculate_recall_at_k(retrieved_ids, ground_truth_ids, 3),
        recall_at_5=calculate_recall_at_k(retrieved_ids, ground_truth_ids, 5),
        hit_at_1=calculate_hit_at_k(retrieved_ids, ground_truth_ids, 1),
        hit_at_3=calculate_hit_at_k(retrieved_ids, ground_truth_ids, 3),
        hit_at_5=calculate_hit_at_k(retrieved_ids, ground_truth_ids, 5),
        mrr=calculate_mrr(retrieved_ids, ground_truth_ids),
        context_precision=calculate_context_precision(retrieved_ids, ground_truth_ids, 5),
        context_recall=calculate_context_recall(retrieved_ids, ground_truth_ids),
    )


# ---------------------------------------------------------------------------
# Generation & Citation Metrics
# ---------------------------------------------------------------------------

def calculate_citation_precision(cited_chunk_ids: List[str], ground_truth_chunk_ids: List[str]) -> float:
    """
    Proportion of cited chunks that are truly relevant: |Cited ∩ Relevant| / |Cited|.
    """
    if not cited_chunk_ids:
        return 1.0 if not ground_truth_chunk_ids else 0.0
    gt_set = set(ground_truth_chunk_ids)
    cited_set = set(cited_chunk_ids)
    valid_citations = len(cited_set & gt_set)
    return round(valid_citations / len(cited_set), 4)


def calculate_citation_recall(cited_chunk_ids: List[str], ground_truth_chunk_ids: List[str]) -> float:
    """
    Proportion of relevant chunks that were cited: |Cited ∩ Relevant| / |Relevant|.
    """
    if not ground_truth_chunk_ids:
        return 1.0
    gt_set = set(ground_truth_chunk_ids)
    cited_set = set(cited_chunk_ids)
    hits = len(cited_set & gt_set)
    return round(hits / len(gt_set), 4)


def calculate_abstention_accuracy(is_unanswerable: bool, insufficient_evidence: bool) -> float:
    """
    Evaluate whether the system correctly abstained when evidence is absent,
    or answered when evidence is present.
    """
    if is_unanswerable:
        return 1.0 if insufficient_evidence else 0.0
    return 1.0 if not insufficient_evidence else 0.0


def calculate_verbatim_quote_ratio(answer: str, context_passages: List[str]) -> float:
    """
    Calculate the ratio of answer sentences that contain verbatim quotes (>= 20 chars) from context.
    """
    if not answer or not context_passages:
        return 0.0
    
    # Split into sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 10]
    if not sentences:
        return 0.0

    combined_context = " ".join(context_passages)
    quoted_count = 0

    for sentence in sentences:
        # Strip citation markers like [chunk_id]
        cleaned_sentence = re.sub(r"\[[a-zA-Z0-9_\-]+\]", "", sentence).strip()
        is_quote, _ = CitationService.detect_direct_quote(cleaned_sentence, combined_context, min_chars=20)
        if is_quote:
            quoted_count += 1

    return round(quoted_count / len(sentences), 4)


def calculate_faithfulness(
    answer: str,
    context_passages: List[str],
    is_unanswerable: bool,
    insufficient_evidence: bool
) -> float:
    """
    Calculate faithfulness: the ratio of claims in the generated answer supported by retrieved context.
    If the question is unanswerable and the model abstained, faithfulness is 1.0.
    """
    if is_unanswerable:
        return 1.0 if insufficient_evidence else 0.0

    if insufficient_evidence:
        return 1.0

    if not answer or not context_passages:
        return 0.0

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 10]
    if not sentences:
        return 0.0

    combined_context = " ".join(context_passages).lower()
    supported_sentences = 0

    for sentence in sentences:
        cleaned = re.sub(r"\[[a-zA-Z0-9_\-]+\]", "", sentence).strip().lower()
        words = [w for w in re.findall(r"\w+", cleaned) if len(w) > 3]
        if not words:
            supported_sentences += 1
            continue

        # Check word overlap with context
        matched_words = sum(1 for w in words if w in combined_context)
        overlap_ratio = matched_words / len(words)
        if overlap_ratio >= 0.5:
            supported_sentences += 1

    return round(supported_sentences / len(sentences), 4)


def compute_generation_metrics(
    answer: str,
    cited_chunk_ids: List[str],
    ground_truth_chunk_ids: List[str],
    context_passages: List[str],
    is_unanswerable: bool,
    insufficient_evidence: bool
) -> GenerationMetrics:
    """
    Compute comprehensive generation and citation metrics for a single query.
    """
    return GenerationMetrics(
        faithfulness=calculate_faithfulness(answer, context_passages, is_unanswerable, insufficient_evidence),
        citation_precision=calculate_citation_precision(cited_chunk_ids, ground_truth_chunk_ids),
        citation_recall=calculate_citation_recall(cited_chunk_ids, ground_truth_chunk_ids),
        verbatim_quote_ratio=calculate_verbatim_quote_ratio(answer, context_passages),
        abstention_accuracy=calculate_abstention_accuracy(is_unanswerable, insufficient_evidence),
    )


# ---------------------------------------------------------------------------
# Operational & Aggregate Metrics
# ---------------------------------------------------------------------------

def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """
    Compute Mean, P50 (median), P90, and P95 over a numeric list.
    """
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    mean_val = sum(sorted_vals) / n
    p50_val = percentile(0.50)
    p90_val = percentile(0.90)
    p95_val = percentile(0.95)

    return {
        "mean": round(mean_val, 2),
        "p50": round(p50_val, 2),
        "p90": round(p90_val, 2),
        "p95": round(p95_val, 2),
    }


def aggregate_retrieval_metrics(metrics_list: List[RetrievalMetrics]) -> RetrievalMetrics:
    """
    Compute macro-average retrieval metrics across all items.
    """
    if not metrics_list:
        return RetrievalMetrics()

    n = len(metrics_list)
    return RetrievalMetrics(
        recall_at_1=round(sum(m.recall_at_1 for m in metrics_list) / n, 4),
        recall_at_3=round(sum(m.recall_at_3 for m in metrics_list) / n, 4),
        recall_at_5=round(sum(m.recall_at_5 for m in metrics_list) / n, 4),
        hit_at_1=round(sum(m.hit_at_1 for m in metrics_list) / n, 4),
        hit_at_3=round(sum(m.hit_at_3 for m in metrics_list) / n, 4),
        hit_at_5=round(sum(m.hit_at_5 for m in metrics_list) / n, 4),
        mrr=round(sum(m.mrr for m in metrics_list) / n, 4),
        context_precision=round(sum(m.context_precision for m in metrics_list) / n, 4),
        context_recall=round(sum(m.context_recall for m in metrics_list) / n, 4),
    )


def aggregate_generation_metrics(metrics_list: List[GenerationMetrics]) -> GenerationMetrics:
    """
    Compute macro-average generation metrics across all items.
    """
    if not metrics_list:
        return GenerationMetrics()

    n = len(metrics_list)
    return GenerationMetrics(
        faithfulness=round(sum(m.faithfulness for m in metrics_list) / n, 4),
        citation_precision=round(sum(m.citation_precision for m in metrics_list) / n, 4),
        citation_recall=round(sum(m.citation_recall for m in metrics_list) / n, 4),
        verbatim_quote_ratio=round(sum(m.verbatim_quote_ratio for m in metrics_list) / n, 4),
        abstention_accuracy=round(sum(m.abstention_accuracy for m in metrics_list) / n, 4),
    )
