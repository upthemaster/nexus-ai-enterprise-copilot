"""
Pytest configuration and shared test fixtures for NexusAI backend.

Why: Centralizing test fixtures ensures consistent test isolation, provides
in-memory generators for valid binary documents (PDF, DOCX, TXT), and prevents
disk, ChromaDB, and BM25 index collisions by using temporary directories for all
persistence during test runs.
"""

import io
import pytest
import pytest_asyncio
import docx
from pathlib import Path
from typing import AsyncGenerator
import httpx

from app.main import app
from app.core.config import settings
from app.retrieval.vector_store import VectorStoreManager
from app.retrieval.bm25_index import BM25IndexManager
from app.db.session import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def generate_minimal_valid_pdf(text: str = "NexusAI Enterprise Copilot Valid Test PDF") -> bytes:
    """
    Generate minimal standard-compliant PDF 1.4 binary bytes containing extractable text.
    
    Why: Generating raw PDF bytes directly in-memory avoids heavy external dependencies
    like ReportLab while providing authentic PDF structure for pypdf verification.
    """
    stream_content = f"BT\n/F1 12 Tf\n50 700 Td\n({text}) Tj\nET\n".encode("latin-1")
    stream_length = len(stream_content)

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    
    # Object 1: Catalog
    pos1 = len(pdf)
    pdf.extend(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    
    # Object 2: Pages
    pos2 = len(pdf)
    pdf.extend(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    
    # Object 3: Page
    pos3 = len(pdf)
    pdf.extend(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    
    # Object 4: Content Stream
    pos4 = len(pdf)
    pdf.extend(f"4 0 obj\n<< /Length {stream_length} >>\nstream\n".encode("latin-1"))
    pdf.extend(stream_content)
    pdf.extend(b"endstream\nendobj\n")
    
    # Object 5: Font
    pos5 = len(pdf)
    pdf.extend(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    
    # Cross-reference table
    xref_pos = len(pdf)
    pdf.extend(b"xref\n0 6\n")
    pdf.extend(b"0000000000 65535 f \n")
    pdf.extend(f"{pos1:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"{pos2:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"{pos3:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"{pos4:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"{pos5:010d} 00000 n \n".encode("latin-1"))
    
    # Trailer
    pdf.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    return bytes(pdf)


def generate_valid_docx(text: str = "NexusAI Enterprise Copilot Valid Test DOCX") -> bytes:
    """
    Generate valid in-memory DOCX binary using python-docx.
    """
    doc = docx.Document()
    doc.add_heading("NexusAI Test Document", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def configure_test_environment(tmp_path: Path):
    """
    Isolate file uploads, ChromaDB, and BM25 index storage into temporary test paths.
    
    Why: Prevents test runs from polluting local application data directories
    and guarantees a clean, collision-free state for every test function.
    """
    original_upload_dir = settings.UPLOAD_DIR
    original_chroma_dir = settings.CHROMA_PERSIST_DIR
    original_collection = settings.CHROMA_COLLECTION_NAME
    original_bm25_path = settings.BM25_PERSIST_PATH
    original_sqlite_path = settings.SQLITE_DB_PATH

    settings.UPLOAD_DIR = str(tmp_path / "test_uploads")
    settings.CHROMA_PERSIST_DIR = str(tmp_path / "test_chroma")
    settings.CHROMA_COLLECTION_NAME = f"test_col_{tmp_path.name}"
    settings.BM25_PERSIST_PATH = str(tmp_path / "test_bm25.json")

    test_db_path = tmp_path / "test_nexusai.db"
    settings.SQLITE_DB_PATH = str(test_db_path)
    test_db_url = f"sqlite:///{test_db_path.as_posix()}"
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    VectorStoreManager.reset_instance()
    BM25IndexManager.reset_instance()
    yield
    app.dependency_overrides.pop(get_db, None)
    test_engine.dispose()
    VectorStoreManager.reset_instance()
    BM25IndexManager.reset_instance()
    settings.UPLOAD_DIR = original_upload_dir
    settings.CHROMA_PERSIST_DIR = original_chroma_dir
    settings.CHROMA_COLLECTION_NAME = original_collection
    settings.BM25_PERSIST_PATH = original_bm25_path
    settings.SQLITE_DB_PATH = original_sqlite_path


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Asynchronous HTTPX test client configured with ASGI transport.
    
    Why: Enables testing FastAPI async endpoints with native async HTTP calls
    without requiring a running external network server.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
