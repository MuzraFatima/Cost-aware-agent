import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
import io

from backend.app.main import app
from backend.app.db.session import init_db, SessionLocal
from backend.app.services.knowledge_base import KnowledgeBaseService
from backend.app.agents.rag_agent import RAGAgent
from backend.app.core.router_engine import RouterEngine
from backend.app.db.models import KnowledgeDocument, DocumentChunk

def test_document_parsing_and_chunking():
    sample_text = "CAAR is a Cost-Aware Agent Router. " * 30
    chunks = KnowledgeBaseService.chunk_text(sample_text, chunk_size=200, overlap=30)
    assert len(chunks) > 1
    assert all(len(c) <= 250 for c in chunks)

def test_vector_similarity_search():
    doc_text = "Python programming language for machine learning and artificial intelligence."
    query_match = "Python machine learning"
    query_unrelated = "Baking chocolate chip cookies"
    
    doc_vec = KnowledgeBaseService.compute_vector(doc_text)
    match_vec = KnowledgeBaseService.compute_vector(query_match)
    unrelated_vec = KnowledgeBaseService.compute_vector(query_unrelated)
    
    score_match = KnowledgeBaseService.cosine_similarity(match_vec, doc_vec)
    score_unrelated = KnowledgeBaseService.cosine_similarity(unrelated_vec, doc_vec)
    
    assert score_match > 0.4
    assert score_unrelated == 0.0

def test_ingest_and_search_database():
    init_db()
    with SessionLocal() as db_session:
        filename = "test_policy.txt"
        content = b"The minimum confidence threshold for coding tasks is 0.85 and general Q&A is 0.65."
        
        doc_info = KnowledgeBaseService.ingest_document(filename, content, "text/plain", db_session)
        assert doc_info["filename"] == filename
        assert doc_info["chunk_count"] == 1
        
        # Search vector index
        results = KnowledgeBaseService.search_chunks("What is the coding threshold?", db=db_session, top_k=3, min_similarity=0.15)
        assert len(results) >= 1
        assert results[0]["document_name"] == filename
        assert "0.85" in results[0]["text_snippet"]

@pytest.mark.asyncio
async def test_rag_agent_execution():
    init_db()
    with SessionLocal() as db_session:
        filename = "caar_architecture.md"
        content = b"CAAR routes requests across 4 agent tiers: Cheap, RAG, Frontier, and Consensus."
        KnowledgeBaseService.ingest_document(filename, content, "text/plain", db_session)
        
        rag_agent = RAGAgent()
        rag_agent.mock_mode = True
        
        result = await rag_agent.execute(
            prompt="What are the 4 agent tiers in CAAR?",
            db=db_session
        )
        
        assert result["rag_used"] is True
        assert len(result["sources"]) >= 1
        assert result["sources"][0]["document_name"] == filename
        assert "Sources:" in result["text"]

@pytest.mark.asyncio
async def test_router_cost_aware_rag():
    init_db()
    with SessionLocal() as db_session:
        filename = "pricing_spec.txt"
        content = b"Commodity models cost $0.0001 per 1000 tokens while frontier models cost $0.002."
        KnowledgeBaseService.ingest_document(filename, content, "text/plain", db_session)
        
        router = RouterEngine(mock_mode=True)
        
        # RAG Query: Matching document content
        rag_result = await router.route(
            prompt="What is the cost of commodity models in pricing spec?",
            db=db_session
        )
        
        assert rag_result["rag_used"] is True
        assert len(rag_result["sources"]) >= 1
        assert "knowledge base" in rag_result["routing_reason"].lower() or "retrieved" in rag_result["routing_reason"].lower()

@pytest.mark.asyncio
async def test_rag_api_endpoints():
    init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        # 1. Upload Document
        file_bytes = b"CAAR system design document detailing RAG knowledge base integration."
        files = {"file": ("system_design.txt", file_bytes, "text/plain")}
        upload_res = await async_client.post("/api/v1/rag/documents/upload", files=files)
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["status"] == "success"
        doc_id = upload_data["document"]["id"]
        
        # 2. List Documents
        list_res = await async_client.get("/api/v1/rag/documents")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total_documents"] >= 1
        
        # 3. Search Vector Index
        search_res = await async_client.post("/api/v1/rag/search", json={"query": "RAG knowledge base system design", "top_k": 3})
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["matches_count"] >= 1
        
        # 4. Delete Document
        del_res = await async_client.delete(f"/api/v1/rag/documents/{doc_id}")
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["status"] == "success"
