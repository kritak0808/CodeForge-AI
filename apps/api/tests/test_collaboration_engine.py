import os
import sys
import uuid
import pytest
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure paths are added
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
workers_path = os.path.join(workspace_root, "apps", "agent-workers")
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)
if workers_path not in sys.path:
    sys.path.insert(0, workers_path)

from app.models import (
    User, Project, Workflow, WorkflowState,
    AgentCollaborationSession, AgentConversation, AgentMessage,
    AgentReview, AgentVote, AgentConflict, AgentResolution
)
from app.services.collaboration import CollaborationService
from app.repositories.collaboration import (
    AgentCollaborationSessionRepository, AgentConversationRepository, AgentMessageRepository,
    AgentReviewRepository, AgentVoteRepository, AgentConflictRepository, AgentResolutionRepository
)
from workflow_manager import WorkflowManager
from agent import (
    messaging_tool, peer_review_tool, conflict_resolution_tool,
    voting_tool, consensus_tool, memory_exchange_tool
)

async def _get_auth_headers(client: AsyncClient) -> dict:
    """Helper to register and login a user, returning Authorization headers."""
    username = f"user_{uuid.uuid4().hex[:8]}"
    reg_payload = {
        "username": username,
        "email": f"{username}@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    login_payload = {
        "username": username,
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ── 1. REST API & Endpoint Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collaboration_rest_flow(client: AsyncClient, db_session: AsyncSession):
    headers = await _get_auth_headers(client)

    # Setup project and workflow
    user_query = select(User).limit(1)
    res_user = await db_session.execute(user_query)
    user_obj = res_user.scalars().first()
    
    project = Project(user_id=user_obj.user_id, name="CollabProj", tech_stack={})
    db_session.add(project)
    await db_session.commit()

    workflow = Workflow(workflow_id=uuid.uuid4(), project_id=project.project_id, current_state="PLANNING")
    db_session.add(workflow)
    await db_session.commit()

    # 1. POST /collaboration/start
    start_payload = {
        "project_id": str(project.project_id),
        "workflow_id": str(workflow.workflow_id)
    }
    start_resp = await client.post("/api/v1/collaboration/start", json=start_payload, headers=headers)
    assert start_resp.status_code == 201
    start_data = start_resp.json()
    session_id = start_data["session_id"]
    assert session_id is not None
    assert start_data["status"] == "ACTIVE"

    # Fetch session to get conversation_id
    session_query = select(AgentConversation).filter(AgentConversation.session_id == uuid.UUID(session_id))
    res_conv = await db_session.execute(session_query)
    conv_obj = res_conv.scalars().first()
    assert conv_obj is not None
    conversation_id = str(conv_obj.conversation_id)

    # 2. POST /collaboration/message
    msg_payload = {
        "conversation_id": conversation_id,
        "sender_agent": "ArchitectAgent",
        "recipient_agent": "DatabaseAgent",
        "content": "Let's align on table structures",
        "message_metadata": {"importance": "high"}
    }
    msg_resp = await client.post("/api/v1/collaboration/message", json=msg_payload, headers=headers)
    assert msg_resp.status_code == 201
    msg_data = msg_resp.json()
    message_id = msg_data["message_id"]
    assert message_id is not None
    assert msg_data["content"] == "Let's align on table structures"

    # 3. GET /collaboration/messages/{id}
    get_msg_resp = await client.get(f"/api/v1/collaboration/messages/{message_id}", headers=headers)
    assert get_msg_resp.status_code == 200
    assert get_msg_resp.json()["sender_agent"] == "ArchitectAgent"

    # 4. POST /collaboration/review (Create + Approve)
    artifact_id = uuid.uuid4()
    review_payload = {
        "session_id": session_id,
        "reviewer_agent": "BackendAgent",
        "target_agent": "DatabaseAgent",
        "artifact_type": "DatabaseDesign",
        "artifact_id": str(artifact_id),
        "status": "APPROVED",
        "comments": "The design looks complete and matches requirements"
    }
    rev_resp = await client.post("/api/v1/collaboration/review", json=review_payload, headers=headers)
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    review_id = rev_data["review_id"]
    assert review_id is not None
    assert rev_data["status"] == "APPROVED"

    # 5. GET /collaboration/reviews/{id}
    get_rev_resp = await client.get(f"/api/v1/collaboration/reviews/{review_id}", headers=headers)
    assert get_rev_resp.status_code == 200
    assert get_rev_resp.json()["reviewer_agent"] == "BackendAgent"

    # 6. POST /collaboration/vote
    vote_payload = {
        "session_id": session_id,
        "topic": "Use PostgreSQL JSONB",
        "voter_agent": "BackendAgent",
        "decision": "YES"
    }
    vote_resp = await client.post("/api/v1/collaboration/vote", json=vote_payload, headers=headers)
    assert vote_resp.status_code == 201
    vote_data = vote_resp.json()
    assert vote_data["vote_id"] is not None
    assert vote_data["decision"] == "YES"

    # 7. POST /collaboration/conflict
    conflict_payload = {
        "session_id": session_id,
        "title": "FastAPI vs Go backend",
        "description": "Backend and Architect agents disagree on implementation language",
        "severity": "HIGH"
    }
    conf_resp = await client.post("/api/v1/collaboration/conflict", json=conflict_payload, headers=headers)
    assert conf_resp.status_code == 201
    conf_data = conf_resp.json()
    conflict_id = conf_data["conflict_id"]
    assert conflict_id is not None
    assert conf_data["status"] == "OPEN"

    # 8. POST /collaboration/resolve
    resolve_payload = {
        "conflict_id": conflict_id,
        "resolved_by": "LeadAgent",
        "resolution_strategy": "Lead Agent Arbitration",
        "details": "Lead agent chose FastAPI due to Python requirements"
    }
    resol_resp = await client.post("/api/v1/collaboration/resolve", json=resolve_payload, headers=headers)
    assert resol_resp.status_code == 200
    resol_data = resol_resp.json()
    assert resol_data["status"] == "RESOLVED"

    # 9. GET /collaboration/sessions/{id}
    sess_resp = await client.get(f"/api/v1/collaboration/sessions/{session_id}", headers=headers)
    assert sess_resp.status_code == 200
    sess_data = sess_resp.json()
    assert sess_data["status"] == "ACTIVE"
    assert len(sess_data["conversations"]) == 1

# ── 2. Specialist Agent Tools Tests ──────────────────────────────────────────

def test_collaboration_agent_tools():
    # Test messaging_tool
    msg_res = messaging_tool(
        conversation_id="conv-123",
        sender_agent="FrontendAgent",
        recipient_agent="BackendAgent",
        content="Verify API routes"
    )
    assert msg_res["conversation_id"] == "conv-123"
    assert msg_res["content"] == "Verify API routes"

    # Test peer_review_tool
    rev_res = peer_review_tool(
        session_id="session-123",
        reviewer_agent="QAAgent",
        target_agent="FrontendAgent",
        artifact_type="UI Dashboard",
        artifact_id="art-456",
        status="REWORK_REQUESTED",
        comments="Alignment is off on mobile viewports"
    )
    assert rev_res["status"] == "REWORK_REQUESTED"
    assert rev_res["reviewer_agent"] == "QAAgent"

    # Test conflict_resolution_tool
    conf_res = conflict_resolution_tool(
        conflict_id="conf-789",
        resolved_by="GovernanceEngine",
        resolution_strategy="Escalation to Governance",
        details="Timeout triggered dynamic delegation"
    )
    assert conf_res["conflict_id"] == "conf-789"
    assert conf_res["resolved_by"] == "GovernanceEngine"

    # Test voting_tool
    vote_res = voting_tool(
        session_id="session-123",
        topic="FastAPI framework",
        voter_agent="ArchitectAgent",
        decision="YES"
    )
    assert vote_res["topic"] == "FastAPI framework"
    assert vote_res["decision"] == "YES"

    # Test consensus_tool
    votes = [
        {"decision": "YES"},
        {"decision": "YES"},
        {"decision": "NO"}
    ]
    con_res = consensus_tool(topic="Adopt Vite", votes=votes)
    assert con_res["consensus_outcome"] == "APPROVED"
    assert con_res["yes_votes"] == 2
    assert con_res["total_votes"] == 3

    # Test memory_exchange_tool
    pool = {"framework": "FastAPI", "version": "0.110.0"}
    mem_res = memory_exchange_tool(pool=pool, key="version")
    assert mem_res["value"] == "0.110.0"

    mem_res_update = memory_exchange_tool(pool=pool, key="version", value="0.115.0")
    assert mem_res_update["value"] == "0.115.0"
    assert mem_res_update["pool"]["version"] == "0.115.0"

# ── 3. Orchestrator Callbacks & State Persistence Tests ──────────────────────

def test_orchestrator_collaboration_callbacks():
    # Setup workflow & project records in sync SQLite memory db
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    user = User(username="testcollab", email="testcollab@codeforge.ai", password_hash="pass", role="developer")
    db_session.add(user)
    db_session.commit()

    project = Project(user_id=user.user_id, name="OrchCollabProj", tech_stack={})
    db_session.add(project)
    db_session.commit()

    workflow = Workflow(workflow_id=uuid.uuid4(), project_id=project.project_id, current_state="PLANNING")
    db_session.add(workflow)
    db_session.commit()

    session = AgentCollaborationSession(
        session_id=uuid.uuid4(),
        project_id=project.project_id,
        workflow_id=workflow.workflow_id,
        status="ACTIVE"
    )
    db_session.add(session)
    db_session.commit()

    # Prevent session.close() from closing the shared session during tests
    original_close = db_session.close
    db_session.close = lambda: None

    # Instantiate WorkflowManager
    db_url = "sqlite://"
    redis_url = "redis://localhost:6379/0"
    mock_pub = MagicMock()
    
    manager = WorkflowManager(db_url=db_url, redis_url=redis_url, event_pub=mock_pub)
    manager.checkpoint_mgr.SessionLocal = lambda: db_session

    # Save initial checkpoint
    manager.checkpoint_mgr.save_checkpoint(
        workflow_id=str(workflow.workflow_id),
        current_node="PLANNING",
        execution_context={"project_id": str(project.project_id)},
        agent_outputs={}
    )

    # Mark active execution as PAUSED simulating orchestrator waiting on collaboration
    manager.active_executions[str(workflow.workflow_id)] = "PAUSED"

    # Test 1: on_agent_review_requested
    review_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    ok = manager.on_agent_review_requested(
        session_id=str(session.session_id),
        review_id=review_id,
        reviewer_agent="QAAgent",
        target_agent="FrontendAgent",
        artifact_type="DashboardsUI",
        artifact_id=artifact_id
    )
    assert ok is True

    # Retrieve checkpoint and assert review requested state is saved
    cp = manager.checkpoint_mgr.restore_checkpoint(str(workflow.workflow_id))
    assert cp is not None
    reviews = cp["execution_context"]["collaboration"]["reviews"]
    assert review_id in reviews
    assert reviews[review_id]["status"] == "PENDING"
    assert reviews[review_id]["reviewer_agent"] == "QAAgent"

    # Test 2: on_agent_review_completed (REWORK_REQUESTED)
    ok_comp = manager.on_agent_review_completed(
        session_id=str(session.session_id),
        review_id=review_id,
        reviewer_agent="QAAgent",
        status="REWORK_REQUESTED"
    )
    assert ok_comp is True

    cp = manager.checkpoint_mgr.restore_checkpoint(str(workflow.workflow_id))
    assert cp["execution_context"]["collaboration"]["reviews"][review_id]["status"] == "REWORK_REQUESTED"
    # Verify rework request error is appended
    assert len(cp["errors"]) > 0

    # Test 3: on_agent_vote_completed
    ok_vote = manager.on_agent_vote_completed(
        session_id=str(session.session_id),
        topic="fastapi_version",
        voter_agent="ArchitectAgent",
        decision="YES"
    )
    assert ok_vote is True

    cp = manager.checkpoint_mgr.restore_checkpoint(str(workflow.workflow_id))
    assert cp["execution_context"]["collaboration"]["votes"]["fastapi_version"]["ArchitectAgent"] == "YES"

    # Test 4: on_agent_conflict_resolved
    conflict_id = str(uuid.uuid4())
    ok_conf = manager.on_agent_conflict_resolved(
        session_id=str(session.session_id),
        conflict_id=conflict_id,
        resolved_by="LeadAgent",
        strategy="Lead Arbitration"
    )
    assert ok_conf is True

    cp = manager.checkpoint_mgr.restore_checkpoint(str(workflow.workflow_id))
    assert cp["execution_context"]["collaboration"]["conflicts"][conflict_id]["status"] == "RESOLVED"

    # Test 5: on_agent_collaboration_completed
    # This transitions execution status from PAUSED back to RUNNING and runs next steps
    # We patch run_workflow_step to avoid executing graph during test
    with patch.object(manager, "run_workflow_step") as mock_step:
        ok_coll = manager.on_agent_collaboration_completed(
            workflow_id=str(workflow.workflow_id),
            session_id=str(session.session_id)
        )
        assert ok_coll is True
        mock_step.assert_called_once_with(str(workflow.workflow_id))

    assert manager.active_executions[str(workflow.workflow_id)] == "RUNNING"
    cp = manager.checkpoint_mgr.restore_checkpoint(str(workflow.workflow_id))
    assert cp["execution_context"]["collaboration_status"] == "COMPLETED"
    assert cp["agent_outputs"]["CollaborationSession"]["status"] == "COMPLETED"

    original_close()
