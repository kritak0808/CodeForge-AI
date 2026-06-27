import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Project, User, Workflow, Approval
from shared_memory.rag import ParentChildChunker, HybridRetriever
from shared_memory.qdrant import QdrantManager
import sys
import os
# Resolve paths to agent-orchestrator and agent-workers due to hyphenated folder names
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
workers_path = os.path.join(workspace_root, "apps", "agent-workers")

if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)
if workers_path not in sys.path:
    sys.path.insert(0, workers_path)

from workflow import build_workflow_graph
from agent import ResearchAgent


def test_parent_child_chunker():
    """
    Verifies that text chunking splits parents and children with overlap correctly.
    """
    text = "This is header one.\n\n" + "Word " * 500 + "\n\nThis is header two.\n\n" + "Test " * 400
    chunks = ParentChildChunker.chunk_document(text)
    
    assert len(chunks) > 0
    # Assert child format contains identifiers
    for chunk in chunks:
        assert "child_id" in chunk
        assert "parent_id" in chunk
        assert "child_text" in chunk
        assert "parent_text" in chunk
        # Children should refer to parent text (normalized for whitespace)
        assert "".join(chunk["child_text"].split()) in "".join(chunk["parent_text"].split())

def test_qdrant_manager_in_memory():
    """
    Verifies that the in-memory Qdrant instance starts and saves vectors correctly.
    """
    mgr = QdrantManager()
    collection_name = "test_collection"
    
    import asyncio
    created = asyncio.run(mgr.create_collection_if_not_exists(collection_name, vector_size=4))
    assert created is True
    
    # Upsert vectors
    pt_id = uuid.uuid4()
    mgr.upsert_vectors(collection_name, [{
        "id": pt_id,
        "vector": [0.1, 0.2, 0.3, 0.4],
        "payload": {"info": "test"}
    }])
    
    # Query similarity
    results = mgr.search_similarity(collection_name, [0.15, 0.22, 0.31, 0.44], limit=1)
    assert len(results) == 1
    assert results[0]["payload"]["info"] == "test"

def test_langgraph_workflow_compilation():
    """
    Verifies that the LangGraph workflow structure compiles cleanly.
    """
    graph = build_workflow_graph()
    assert graph is not None
    # LangGraph objects should have nodes and edges
    assert hasattr(graph, "nodes") or hasattr(graph, "get_graph")

def test_research_agent_execution():
    """
    Verifies that the Research Agent correctly compiles framework research reports.
    """
    agent = ResearchAgent()
    res = agent.execute_task("Research best patterns for FastAPI database connection pooling.")
    
    assert res["status"] == "COMPLETED"
    assert "Technology Recommendation Report" in res["output"]
    assert "FastAPI Docs" in res["output"]

@pytest.mark.asyncio
async def test_workflow_rest_endpoints(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies HTTP routes for workflow triggering, status inspections, and approval decisions.
    """
    # 1. Register and Login Owner
    reg_payload = {
        "username": "workflowdev",
        "email": "workflowdev@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    login_payload = {
        "username": "workflowdev",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Project
    proj_payload = {
        "name": "OrchestratorTest",
        "description": "Integration testing project",
        "tech_stack": {"backend": "FastAPI", "frontend": "Next.js"},
        "budget_usd_limit": 100.00
    }
    proj_resp = await client.post("/api/v1/projects/", json=proj_payload, headers=headers)
    project_id = proj_resp.json()["data"]["project_id"]

    # 3. Trigger Workflow Run
    trigger_payload = {
        "project_id": project_id,
        "requirements": "Build user auth modules."
    }
    trig_resp = await client.post("/api/v1/workflows/", json=trigger_payload, headers=headers)
    assert trig_resp.status_code == 201
    assert trig_resp.json()["success"] is True
    workflow_id = trig_resp.json()["data"]["workflow_id"]

    # 4. Get Status
    status_resp = await client.get(f"/api/v1/workflows/{workflow_id}/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["success"] is True
    assert status_resp.json()["data"]["current_state"] == "CREATED"

    # 5. Insert mock approval and submit decision
    from sqlalchemy import select
    user_query = select(User).filter(User.username == "workflowdev")
    res = await db_session.execute(user_query)
    db_user = res.scalars().first()
    
    approval_obj = Approval(
        workflow_id=uuid.UUID(workflow_id),
        approval_type="Database",
        status="PENDING",
        artifact_payload={"schema": "CREATE TABLE test;"}
    )

    db_session.add(approval_obj)
    await db_session.commit()
    await db_session.refresh(approval_obj)

    dec_payload = {
        "status": "APPROVED",
        "comments": "Matches architectural specifications perfectly."
    }
    dec_resp = await client.post(
        f"/api/v1/workflows/approvals/{approval_obj.approval_id}/decision",
        json=dec_payload,
        headers=headers
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["success"] is True
    assert dec_resp.json()["data"]["status"] == "APPROVED"
