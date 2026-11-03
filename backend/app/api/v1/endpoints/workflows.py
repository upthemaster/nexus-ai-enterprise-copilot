"""
LangGraph workflow endpoints.

Why: Thin HTTP routing layer exposing unified workflow execution with automatic query routing,
evidence retrieval, reranking, and grounded response synthesis.
"""

from fastapi import APIRouter, status
from app.schemas.workflow import WorkflowRequest, WorkflowResponse
from app.services.workflow_service import WorkflowService

router = APIRouter()


@router.post(
    "/run",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute LangGraph workflow with query routing",
    description=(
        "Executes a stateful LangGraph workflow. Automatically classifies intent (or uses requested_workflow_type) "
        "and routes execution to Q&A, Summarization, or Risk Extraction branches with verified citations."
    )
)
def run_workflow(request: WorkflowRequest) -> WorkflowResponse:
    """
    Run the multi-step LangGraph workflow.
    """
    return WorkflowService.run_workflow(request=request)

