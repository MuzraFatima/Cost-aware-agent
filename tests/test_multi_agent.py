import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import init_db, SessionLocal
from backend.app.agents.coding_agent import CodingAgent
from backend.app.agents.research_agent import ResearchAgent
from backend.app.agents.analysis_agent import AnalysisAgent
from backend.app.core.multi_agent_coordinator import MultiAgentCoordinator, multi_agent_coordinator
from backend.app.core.router_engine import RouterEngine

@pytest.mark.asyncio
async def test_specialized_coding_agent():
    agent = CodingAgent()
    agent.mock_mode = True
    res = await agent.execute("Write a python function to check prime number")
    assert res["specialization"] == "coding"
    assert "def " in res["text"] or "prime" in res["text"].lower()

@pytest.mark.asyncio
async def test_specialized_research_agent():
    agent = ResearchAgent()
    agent.mock_mode = True
    res = await agent.execute("Research multi-agent reinforcement learning system design")
    assert res["specialization"] == "research"
    assert "Research" in res["model_name"] or "Report" in res["text"]

@pytest.mark.asyncio
async def test_specialized_analysis_agent():
    agent = AnalysisAgent()
    agent.mock_mode = True
    res = await agent.execute("Analyze server log response time metrics")
    assert res["specialization"] == "analysis"
    assert "Analysis" in res["model_name"]

def test_multi_agent_coordinator_registry():
    registry = multi_agent_coordinator.get_registry()
    assert len(registry) == 7
    specializations = {a["specialization"] for a in registry}
    assert {"coding", "research", "analysis", "general", "rag", "consensus"}.issubset(specializations)

@pytest.mark.asyncio
async def test_router_specialized_domain_dispatch():
    init_db()
    router = RouterEngine(mock_mode=True)
    with SessionLocal() as db:
        # Coding dispatch
        coding_res = await router.route("Write a python function to sort a list", domain="coding", db=db)
        assert coding_res["task_type"] == "coding"
        
        # Research dispatch
        research_res = await router.route("Multi-agent architecture security audit and comparative analysis", domain="research", db=db)
        assert research_res["task_type"] == "research"

@pytest.mark.asyncio
async def test_agents_registry_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        res = await async_client.get("/api/v1/agents/registry")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["total_agents"] == 7
        assert len(data["agents"]) == 7
