"""
Citation inspection API endpoints.

Why: Exposes GET /api/v1/citations/{chunk_id} enabling UI citation click-throughs
and full source text inspection, adhering to Table 3 (US-03) and Table 9 of the Master Blueprint.
"""

import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.citation import SourceInspectorResponse
from app.services.citation_service import CitationService

logger = logging.getLogger("nexusai.api.citations")

router = APIRouter()


@router.get(
    "/{chunk_id}",
    response_model=SourceInspectorResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect full source passage by chunk ID",
    description="Retrieves the exact chunk text, page number, and document metadata for UI source inspection."
)
async def inspect_source_chunk(chunk_id: str) -> SourceInspectorResponse:
    """
    Fetch full chunk content for source evidence verification.
    """
    result = CitationService.get_source_chunk(chunk_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source chunk '{chunk_id}' not found."
        )
    return result

