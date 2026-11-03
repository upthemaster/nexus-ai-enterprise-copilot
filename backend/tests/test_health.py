"""
Tests for system health check endpoint.

Why: Confirms that the health check endpoint adheres to the API contract
without exposing internal server states or system paths.
"""

import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check_success(async_client: httpx.AsyncClient):
    """
    Test GET /api/v1/health returns HTTP 200 with valid operational status.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data

