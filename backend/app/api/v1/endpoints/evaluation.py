"""
Evaluation and benchmark API endpoints.

Why: Exposes HTTP endpoints for triggering automated evaluation runs, retrieving historical
benchmark summaries, and running 4-way retrieval ablation experiments as defined in Master Blueprint Section 11.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunSummary,
    AblationComparisonResponse,
    RetrievalConfig,
)
from app.services.evaluation_service import EvaluationService

logger = logging.getLogger("nexusai.api.evaluation")

router = APIRouter(prefix="/evaluation", tags=["Evaluation & Benchmarks"])


@router.post(
    "/run",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Automated Evaluation Run",
    description="Executes quantitative evaluation of retrieval and grounded generation against a golden dataset."
)
async def run_evaluation(request: EvaluationRunRequest) -> EvaluationRunResponse:
    """
    Execute an automated evaluation run.
    """
    try:
        return EvaluationService.execute_evaluation(request)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Evaluation run failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation execution failed: {str(e)}"
        )


@router.get(
    "/ablation",
    response_model=AblationComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Run 4-Way Retrieval Ablation Benchmark",
    description="Compares Vector-Only, BM25-Only, Hybrid RRF, and Hybrid + Cross-Encoder Reranking."
)
async def run_ablation(
    dataset_version: str = Query(default="v1", description="Dataset version identifier"),
    top_k: int = Query(default=5, ge=1, le=20, description="Candidate retrieval count")
) -> AblationComparisonResponse:
    """
    Execute 4-way retrieval ablation comparison across all architectural configurations.
    """
    try:
        return EvaluationService.execute_ablation(
            dataset_version=dataset_version,
            top_k=top_k
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Ablation benchmark failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ablation benchmark execution failed: {str(e)}"
        )


@router.get(
    "/runs",
    response_model=List[EvaluationRunSummary],
    status_code=status.HTTP_200_OK,
    summary="List Evaluation Run Summaries",
    description="Retrieves a list of historical evaluation runs with aggregate metrics."
)
async def list_evaluation_runs() -> List[EvaluationRunSummary]:
    """
    List all recorded evaluation runs.
    """
    return EvaluationService.list_runs()


@router.get(
    "/runs/{run_id}",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation Run Details",
    description="Retrieves full query-by-query breakdown for a specific evaluation run."
)
async def get_evaluation_run(run_id: str) -> EvaluationRunResponse:
    """
    Retrieve full evaluation report by run ID.
    """
    run_response = EvaluationService.get_run(run_id)
    if not run_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{run_id}' not found."
        )
    return run_response

