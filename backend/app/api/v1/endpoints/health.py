"""
Health check endpoint.

Why: Providing a lightweight, unauthenticated health endpoint enables container
orchestrators (Docker, Kubernetes) and load balancers to query liveness and readiness
without leaking environment variables, internal paths, or credentials.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Returns service availability, application version, and timestamp."
)
async def get_health() -> HealthResponse:
    """
    Query system health and operational readiness.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat()
    )

