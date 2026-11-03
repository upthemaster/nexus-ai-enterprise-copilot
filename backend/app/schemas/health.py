"""
Health check schema models.

Why: Defining strongly typed response contracts guarantees predictable API
behavior and automatic OpenAPI schema generation for infrastructure probes.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Response schema for the system health status endpoint.
    
    Why: Keeps status reporting consistent and lightweight without revealing
    internal server topology, credentials, or file paths.
    """
    status: str = Field(default="healthy", description="Overall service operational health")
    version: str = Field(default="0.1.0", description="Backend service semantic version")
    timestamp: str = Field(description="ISO-8601 formatted timestamp of the health check")

