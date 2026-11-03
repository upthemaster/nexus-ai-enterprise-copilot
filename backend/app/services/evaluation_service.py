"""
Evaluation service coordinating corpus seeding, benchmark execution, and persistent run tracking.

Why: Exposes a unified service layer for evaluation endpoints, automated test harnesses,
and regression monitoring, ensuring separation of concerns between API routes and benchmark math.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunSummary,
    AblationComparisonResponse,
    GoldenDatasetItem,
)
from app.evaluation.dataset import load_golden_dataset, seed_evaluation_corpus
from app.evaluation.benchmarks import BenchmarkRunner
from app.retrieval.bm25_index import get_bm25_manager

logger = logging.getLogger("nexusai.services.evaluation")

EVAL_RUNS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "eval_runs"


class EvaluationService:
    """
    Manages evaluation runs, ablation comparisons, and historical run persistence.
    """

    _runs_cache: Dict[str, EvaluationRunResponse] = {}
    _corpus_seeded: bool = False

    @classmethod
    def ensure_corpus_seeded(cls, force: bool = False) -> None:
        """
        Verify that the evaluation corpus is indexed in ChromaDB and BM25.
        """
        if cls._corpus_seeded and not force:
            return

        # Check if any eval chunks exist in BM25 or Chroma
        bm25 = get_bm25_manager()
        if not force and bm25.count() > 0 and any("eval_" in c.chunk_id for c in bm25._chunks):
            cls._corpus_seeded = True
            return

        logger.info("Seeding evaluation corpus into VectorStore and BM25Index...")
        seed_evaluation_corpus()
        cls._corpus_seeded = True

    @classmethod
    def get_runs_dir(cls) -> Path:
        """
        Ensure evaluation runs directory exists on local disk.
        """
        EVAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
        return EVAL_RUNS_DIR

    @classmethod
    def persist_run(cls, response: EvaluationRunResponse) -> None:
        """
        Save evaluation run response to in-memory cache and disk.
        """
        run_id = response.summary.run_id
        cls._runs_cache[run_id] = response

        try:
            runs_dir = cls.get_runs_dir()
            run_file = runs_dir / f"{run_id}.json"
            run_file.write_text(response.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist evaluation run %s to disk: %s", run_id, e)

    @classmethod
    def execute_evaluation(cls, request: EvaluationRunRequest) -> EvaluationRunResponse:
        """
        Execute an automated evaluation run on demand.
        """
        cls.ensure_corpus_seeded()
        items = load_golden_dataset(request.dataset_version)

        logger.info(
            "Executing evaluation run for dataset '%s' (%d items) with config '%s' (include_generation=%s)",
            request.dataset_version,
            len(items),
            request.retrieval_config.value,
            request.include_generation
        )

        response = BenchmarkRunner.run_evaluation(
            items=items,
            config=request.retrieval_config,
            include_generation=request.include_generation,
            top_k=request.top_k,
            dataset_version=request.dataset_version
        )

        cls.persist_run(response)
        return response

    @classmethod
    def execute_ablation(
        cls,
        dataset_version: str = "v1",
        top_k: int = 5
    ) -> AblationComparisonResponse:
        """
        Execute the 4-way retrieval ablation benchmark across all 4 architectures.
        """
        cls.ensure_corpus_seeded()
        items = load_golden_dataset(dataset_version)

        logger.info(
            "Executing 4-way retrieval ablation on dataset '%s' (%d items, top_k=%d)",
            dataset_version,
            len(items),
            top_k
        )

        return BenchmarkRunner.run_ablation_comparison(
            items=items,
            top_k=top_k,
            dataset_version=dataset_version
        )

    @classmethod
    def list_runs(cls) -> List[EvaluationRunSummary]:
        """
        List summaries of all past evaluation runs from disk and cache.
        """
        runs_dir = cls.get_runs_dir()
        summaries: List[EvaluationRunSummary] = []

        # Read persisted disk files
        for run_file in sorted(runs_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(run_file.read_text(encoding="utf-8"))
                summary = EvaluationRunSummary(**data["summary"])
                summaries.append(summary)
            except Exception as e:
                logger.warning("Could not read run file %s: %s", run_file.name, e)

        # Merge with any memory-only runs
        known_ids = {s.run_id for s in summaries}
        for run_id, run_resp in cls._runs_cache.items():
            if run_id not in known_ids:
                summaries.append(run_resp.summary)

        return summaries

    @classmethod
    def get_run(cls, run_id: str) -> Optional[EvaluationRunResponse]:
        """
        Retrieve complete report for a specific evaluation run.
        """
        if run_id in cls._runs_cache:
            return cls._runs_cache[run_id]

        runs_dir = cls.get_runs_dir()
        run_file = runs_dir / f"{run_id}.json"
        if run_file.exists():
            try:
                data = json.loads(run_file.read_text(encoding="utf-8"))
                resp = EvaluationRunResponse(**data)
                cls._runs_cache[run_id] = resp
                return resp
            except Exception as e:
                logger.error("Failed to parse evaluation run file %s: %s", run_file, e)

        return None
