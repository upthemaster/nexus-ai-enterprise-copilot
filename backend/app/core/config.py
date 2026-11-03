"""
Core application settings for NexusAI Enterprise Copilot.

This module uses pydantic-settings to manage environment-based configuration.
Decoupling configuration from code ensures twelve-factor app compliance and
prevents hardcoding sensitive or environment-specific values.
"""

from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and/or .env file.
    
    Why: Centralizing configuration prevents scattered os.getenv calls across
    the codebase, guarantees strict type validation at boot time, and provides
    safe defaults for local development.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General Application Info
    APP_NAME: str = Field(default="NexusAI", description="Public name of the application")
    APP_ENV: str = Field(default="development", description="Runtime environment (development, staging, production)")
    DEBUG: bool = Field(default=False, description="Enable debug mode (never enabled in production)")
    HOST: str = Field(default="0.0.0.0", description="Host address for ASGI server")
    PORT: int = Field(default=8000, description="Listening port for ASGI server")

    # Ingestion & File Constraints (Day 1)
    MAX_FILE_SIZE_MB: int = Field(
        default=10,
        description="Maximum permitted upload file size in megabytes to prevent memory exhaustion"
    )
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=["pdf", "docx", "txt"],
        description="Strict whitelist of allowed document file extensions"
    )
    UPLOAD_DIR: str = Field(
        default="./data/uploads",
        description="Base filesystem directory for storing ingested files"
    )

    # Chunking Configuration (Day 2)
    CHUNK_SIZE: int = Field(
        default=500,
        description="Target maximum character count per text chunk"
    )
    CHUNK_OVERLAP: int = Field(
        default=50,
        description="Character overlap between consecutive chunks to preserve semantic boundaries"
    )

    # Embeddings & Vector Storage (Day 2)
    EMBEDDING_MODEL_NAME: str = Field(
        default="all-MiniLM-L6-v2",
        description="Local SentenceTransformer model for generating dense vector embeddings"
    )
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/chroma",
        description="Filesystem path where ChromaDB persists vector indexes"
    )
    CHROMA_COLLECTION_NAME: str = Field(
        default="nexusai_documents_v1",
        description="Name of the ChromaDB collection for document embeddings"
    )

    # Hybrid Retrieval & BM25 (Day 3)
    RRF_K: int = Field(
        default=60,
        description="Smoothing constant k for Reciprocal Rank Fusion (standard default 60)"
    )
    BM25_PERSIST_PATH: str = Field(
        default="./data/bm25_index.json",
        description="Filesystem path where BM25 index corpus is persisted"
    )

    # Reranking & LLM Generation (Day 4)
    RERANKER_MODEL_NAME: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="HuggingFace Cross-Encoder model name for second-stage passage reranking"
    )
    RERANKER_TOP_K: int = Field(
        default=3,
        description="Default number of passages to retain after cross-encoder reranking"
    )
    EVIDENCE_MIN_SCORE: float = Field(
        default=-6.0,
        description="Minimum cross-encoder logit score required to consider context sufficient for generation"
    )
    LLM_PROVIDER: str = Field(
        default="gemini",
        description="Active LLM provider adapter: 'gemini', 'openai', or 'mock'"
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for production LLM generation"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Google Gemini model identifier"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key (or key for OpenAI-compatible local endpoint)"
    )
    OPENAI_API_BASE: Optional[str] = Field(
        default=None,
        description="Base URL for OpenAI-compatible endpoint (e.g., http://localhost:11434/v1 for Ollama)"
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier"
    )

    # Relational Database Settings (Day 5)
    SQLITE_DB_PATH: str = Field(
        default="./data/nexusai.db",
        description="Filesystem path where SQLite metadata database is persisted"
    )

    @property
    def max_file_size_bytes(self) -> int:
        """
        Convert MAX_FILE_SIZE_MB to bytes for fast byte-level streaming comparisons.
        
        Why: Calculating this once at the property level eliminates redundant arithmetic
        in performance-critical streaming upload loops.
        """
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        """
        Resolve the UPLOAD_DIR into an absolute Path object and ensure it exists.
        
        Why: Using Pathlib guarantees cross-platform safety (Windows vs POSIX)
        and standardizes directory resolution.
        """
        path = Path(self.UPLOAD_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def chroma_persist_path(self) -> Path:
        """
        Resolve the CHROMA_PERSIST_DIR into an absolute Path object and ensure it exists.
        
        Why: Ensures ChromaDB storage directory is prepared before the client initialises.
        """
        path = Path(self.CHROMA_PERSIST_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def bm25_file_path(self) -> Path:
        """
        Resolve the BM25_PERSIST_PATH into an absolute Path object and ensure parent directory exists.
        
        Why: Ensures parent directory exists before writing BM25 index files.
        """
        path = Path(self.BM25_PERSIST_PATH).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sqlite_db_path(self) -> Path:
        """
        Resolve SQLITE_DB_PATH into an absolute Path object and ensure parent directory exists.
        """
        path = Path(self.SQLITE_DB_PATH).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sqlite_db_url(self) -> str:
        """
        Construct SQLAlchemy connection URL for SQLite.
        """
        # Convert backslashes for cross-platform SQLite URL format
        clean_path = str(self.sqlite_db_path).replace("\\", "/")
        return f"sqlite:///{clean_path}"


# Singleton configuration instance
settings = Settings()
