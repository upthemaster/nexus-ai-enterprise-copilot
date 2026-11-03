"""
API v1 consolidated router.

Why: Centralizes all version 1 route definitions under a single APIRouter.
This allows simple version prefixing (/api/v1) in main.py without repeating
path fragments across endpoint modules.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import health, documents, search, chat, citations, conversations, workflows, evaluation

api_v1_router = APIRouter()

# Mount health routes (/api/v1/health)
api_v1_router.include_router(
    health.router,
    tags=["Health"]
)

# Mount document routes (/api/v1/documents/upload)
api_v1_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"]
)

# Mount search routes (/api/v1/search/vector, /api/v1/search/bm25, /api/v1/search/hybrid)
api_v1_router.include_router(
    search.router,
    prefix="/search",
    tags=["Search"]
)

# Mount chat routes (/api/v1/chat)
api_v1_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)

# Mount citation inspection routes (/api/v1/citations/{chunk_id})
api_v1_router.include_router(
    citations.router,
    prefix="/citations",
    tags=["Citations"]
)

# Mount conversation lifecycle routes (/api/v1/conversations)
api_v1_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"]
)

# Mount LangGraph workflow routes (/api/v1/workflows)
api_v1_router.include_router(
    workflows.router,
    prefix="/workflows",
    tags=["Workflows"]
)

# Mount automated evaluation and ablation routes (/api/v1/evaluation)
api_v1_router.include_router(
    evaluation.router,
    tags=["Evaluation & Benchmarks"]
)

