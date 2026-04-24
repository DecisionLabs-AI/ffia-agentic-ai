# =============================================================================
# FFIA — agent/tools/rag_tool.py
# RAG retrieval tool: indexes invoice cost history and retrieves relevant chunks
# for the ReAct agent using PGVector + VertexAI text-embedding-004.
#
# Architecture: Path B — PGVector manages its own collection table.
# This file does NOT use the invoice_embeddings table created by ensure_rag_schema().
#
# Runtime requirements (must be installed before use):
#   pip install "langchain-postgres>=0.0.12" "psycopg[binary]"
#
# Standalone — not yet wired into agent/main.py.
# =============================================================================

# Step 1: Standard library + env
import os
from contextvars import ContextVar
from dotenv import load_dotenv

# Step 2: LangChain + VertexAI imports
from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_postgres import PGVector

# Step 3: FFIA data layer — available because agent/main.py adds project root to sys.path
from data.db import fetch_invoice_chunks_for_embedding

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# ContextVar — mirrors postgres_tool pattern exactly
# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Tenant context — one per async-safe execution context
_RAG_CURRENT_USER_ID: ContextVar[str | None] = ContextVar("ffia_rag_tool_user_id", default=None)


def set_rag_tool_user_id(user_id: str | None):
    """Bind the current agent run to a tenant for RAG tool isolation."""
    normalized = str(user_id or "").strip() or None
    return _RAG_CURRENT_USER_ID.set(normalized)


def reset_rag_tool_user_id(token) -> None:
    """Restore the previous tenant context after an agent run."""
    _RAG_CURRENT_USER_ID.reset(token)


def get_rag_tool_user_id() -> str | None:
    """Return the current tenant context bound for rag_tool."""
    return _RAG_CURRENT_USER_ID.get()


# ──────────────────────────────────────────────────────────────────────────────
# Lazy singletons — embeddings and vector store initialized on first use
# ──────────────────────────────────────────────────────────────────────────────
_embeddings: VertexAIEmbeddings | None = None
_vector_store: PGVector | None = None


def _get_embeddings() -> VertexAIEmbeddings:
    # Step 5: VertexAI embeddings singleton — auth via GOOGLE_APPLICATION_CREDENTIALS
    global _embeddings
    if _embeddings is None:
        _embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004",
            project=os.environ["GCP_PROJECT_ID"],
            location="asia-southeast1",
        )
    return _embeddings


def _get_connection_string() -> str:
    # Step 6: Convert DATABASE_URL to psycopg3 dialect required by langchain-postgres.
    # langchain-postgres uses psycopg (v3), not psycopg2.
    # Deployment requirement: pip install "psycopg[binary]" before use.
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _get_vector_store() -> PGVector:
    # Step 7: PGVector singleton — manages its own collection table (langchain_pg_collection).
    # Vector dimension (768) is inferred from text-embedding-004 output.
    global _vector_store
    if _vector_store is None:
        _vector_store = PGVector(
            embeddings=_get_embeddings(),
            connection=_get_connection_string(),
            collection_name="invoice_cost_history",
            use_jsonb=True,
        )
    return _vector_store


# ──────────────────────────────────────────────────────────────────────────────
# Step 8: Index all invoice chunks for a tenant
# ──────────────────────────────────────────────────────────────────────────────
def index_invoice_for_user(user_id: str) -> int:
    """Fetch invoice line items for the user and index them in the vector store.

    Returns the number of documents indexed.
    Safe to re-call — duplicate IDs are upserted (ON CONFLICT DO UPDATE).
    """
    # Step 8a: Fetch structured chunks from invoice database
    chunks = fetch_invoice_chunks_for_embedding(user_id)
    if not chunks:
        return 0

    # Step 8b: Wrap each chunk as a LangChain Document with tenant-scoped metadata
    docs: list[Document] = []
    ids: list[str] = []
    for chunk in chunks:
        docs.append(Document(
            page_content=chunk["chunk_text"],
            metadata={
                "user_id":      chunk["user_id"],
                "invoice_id":   chunk["invoice_id"],
                "item_id":      chunk["item_id"],
                "vendor":       chunk["vendor"],
                # invoice_date may be a date object — str() ensures JSONB compatibility
                "invoice_date": str(chunk["invoice_date"]),
            },
        ))
        # Step 8c: Stable document ID — same item always maps to the same vector row
        ids.append(f"{user_id}::item::{chunk['item_id']}")

    # Step 8d: Add to vector store — duplicate IDs are upserted automatically
    _get_vector_store().add_documents(docs, ids=ids)
    return len(docs)


# ──────────────────────────────────────────────────────────────────────────────
# Step 9: RAG retrieval @tool — used by the ReAct agent
# ──────────────────────────────────────────────────────────────────────────────
@tool
def rag_cost_history_tool(query: str) -> str:
    """ค้นหาประวัติต้นทุนวัตถุดิบและใบแจ้งหนี้ที่เกี่ยวข้องกับคำถาม

    ใช้เพื่อดึงข้อมูลต้นทุนจากประวัติใบแจ้งหนี้ของร้าน เช่น ราคาวัตถุดิบ
    ยอดสั่งซื้อ หรือแนวโน้มการเปลี่ยนแปลงราคา
    """
    # Step 9a: Resolve tenant from ContextVar
    user_id = _RAG_CURRENT_USER_ID.get()
    if not user_id:
        return "ไม่สามารถค้นหาได้: ไม่พบข้อมูลผู้ใช้ในบริบทนี้"

    try:
        # Step 9b: Retrieve top-k chunks filtered to this tenant only
        # filter={"user_id": user_id} uses simple equality — equivalent to {"$eq": user_id}
        results = _get_vector_store().similarity_search_with_score(
            query,
            k=8,
            filter={"user_id": user_id},
        )

        if not results:
            return "ไม่พบข้อมูลต้นทุนที่ตรงกับคำถามนี้"

        # Step 9c: Format results as Thai-first user-facing text
        lines = ["พบข้อมูลต้นทุนที่เกี่ยวข้อง:"]
        for doc, score in results:
            lines.append(f"- {doc.page_content}  (คะแนนความเกี่ยวข้อง: {score:.2f})")
        return "\n".join(lines)

    except Exception as e:
        return f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"
