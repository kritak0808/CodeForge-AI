import os
import sys
import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path resolution for apps/agent-orchestrator
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

from app.database import Base
from app.models import Workflow, WorkflowState, Approval, Task, Project, User
from state_models import WorkflowStateModel, TaskMessage, TaskResult, ApprovalRequest
from event_publisher import KafkaEventPublisher
from checkpoint_manager import CheckpointManager
from task_router import TaskRouter
from recovery_manager import RecoveryManager
from approval_handler import ApprovalHandler
from agent_runtime import BaseAgentRuntime
from workflow_manager import WorkflowManager
from graph_builder import compile_sdlc_graph

# Setup local in-memory SQLite for sync components test
@pytest.fixture(name="sync_db")
def sync_db_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Prevent session.close() from closing the shared session during tests
    original_close = session.close
    session.close = lambda: None
    yield session
    original_close()

def test_state_models():
    """
    Unit tests for state and message validation models.
    """
    model = WorkflowStateModel(
        workflow_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        current_state="CREATED",
        workflow_context={"key": "val"},
        cost_metrics={"tokens": 0.05},
        token_metrics={"tokens": 150}
    )
    assert model.current_state == "CREATED"
    assert model.workflow_context["key"] == "val"

    msg = TaskMessage(
        task_id="task-123",
        workflow_id="wf-123",
        agent_id="pm-agent",
        command="analyze"
    )
    assert msg.agent_id == "pm-agent"

    res = TaskResult(
        task_id="task-123",
        workflow_id="wf-123",
        agent_id="pm-agent",
        status="COMPLETED",
        output="PRD draft",
        logs="run successful"
    )
    assert res.status == "COMPLETED"

def test_event_publisher():
    """
    Kafka event publisher offline mode fallback validation.
    """
    pub = KafkaEventPublisher(bootstrap_servers="localhost:9999")
    assert pub.offline_mode is True or pub.producer is None
    
    # Verify fallback logs and runs successfully without raising KafkaErrors
    res = pub.publish("workflow.events", {"event": "test"})
    assert res is False

    # Retry fallback should route to DLQ
    res_retry = pub.retry("workflow.events", {"event": "test"}, max_attempts=2)
    assert res_retry is False

def test_checkpoint_manager(sync_db):
    """
    CheckpointManager saving, restoring, and rollback capabilities.
    """
    db_url = "sqlite://"
    redis_url = "redis://localhost:6379/9"
    mgr = CheckpointManager(db_url=db_url, redis_url=redis_url)
    
    # Overwrite connection engine session for the test
    mgr.SessionLocal = lambda: sync_db

    # Create dummy parent records
    user = User(username="testuser", email="test@test.com", password_hash="pass", role="developer")
    sync_db.add(user)
    sync_db.commit()

    project = Project(user_id=user.user_id, name="TestProj", tech_stack={})
    sync_db.add(project)
    sync_db.commit()

    wf_id = uuid.uuid4()
    workflow = Workflow(workflow_id=wf_id, project_id=project.project_id, current_state="CREATED")
    sync_db.add(workflow)
    sync_db.commit()

    # Save checkpoint
    version = mgr.save_checkpoint(
        workflow_id=str(wf_id),
        current_node="PLANNING",
        execution_context={"req": "test requirements"},
        agent_outputs={"report": "doc specs"}
    )
    assert version == 1

    # Restore checkpoint
    ckpt = mgr.restore_checkpoint(str(wf_id))
    assert ckpt is not None
    assert ckpt["current_node"] == "PLANNING"
    assert ckpt["execution_context"]["req"] == "test requirements"

    # Save second checkpoint
    version2 = mgr.save_checkpoint(
        workflow_id=str(wf_id),
        current_node="RESEARCHING",
        execution_context={"req": "test requirements"},
        agent_outputs={"report": "doc specs", "research": "tech info"}
    )
    assert version2 == 2

    # Rollback to first state
    rolled = mgr.rollback_checkpoint(str(wf_id), "PLANNING")
    assert rolled is True

    # Restore again
    ckpt_after_roll = mgr.restore_checkpoint(str(wf_id))
    assert ckpt_after_roll is not None
    assert ckpt_after_roll["current_node"] == "PLANNING"

def test_task_router():
    """
    TaskRouter dynamic routing rules and retry thresholds.
    """
    pub = KafkaEventPublisher(bootstrap_servers="localhost:9999")
    router = TaskRouter(event_pub=pub, max_retries=2)
    
    # Validate assigned agent mapping
    assert router.get_assigned_agent("PLANNING") == "ProductManagerAgent"
    assert router.get_assigned_agent("RESEARCHING") == "ResearchAgent"
    
    # Test retry outcomes
    outcome1 = router.process_task_failure("t1", "w1", 0, "first error", {})
    assert outcome1["action"] == "RETRY"
    assert outcome1["retry_count"] == 1
    
    # Max retries reached should request DEAD_LETTER DLQ
    outcome2 = router.process_task_failure("t1", "w1", 2, "terminal error", {})
    assert outcome2["action"] == "DEAD_LETTER"

def test_recovery_manager(sync_db):
    """
    RecoveryManager recovery logic and loop limit circuit breaker.
    """
    db_url = "sqlite://"
    redis_url = "redis://localhost:6379/9"
    mgr = CheckpointManager(db_url=db_url, redis_url=redis_url)
    mgr.SessionLocal = lambda: sync_db
    
    recovery = RecoveryManager(db_url=db_url, checkpoint_mgr=mgr, max_rework_cycles=2)
    recovery.SessionLocal = lambda: sync_db

    # User, Project, Workflows Setup
    user = User(username="recuser", email="rec@test.com", password_hash="pass", role="developer")
    sync_db.add(user)
    sync_db.commit()

    project = Project(user_id=user.user_id, name="RecProj", tech_stack={})
    sync_db.add(project)
    sync_db.commit()

    wf_id = uuid.uuid4()
    workflow = Workflow(workflow_id=wf_id, project_id=project.project_id, current_state="PLANNING")
    sync_db.add(workflow)
    sync_db.commit()

    # Save checkpoint
    mgr.save_checkpoint(str(wf_id), "PLANNING", {"project_id": str(project.project_id)}, {})

    # Run recovery scan
    recovered = recovery.recover_interrupted_workflows()
    assert recovered == 1

    # Circuit breaker check
    ctx = {"rework_cycles": {"BACKEND_GENERATION": 1}}
    assert recovery.check_circuit_breaker(str(wf_id), "BACKEND_GENERATION", ctx) is False
    
    recovery.increment_rework_cycle(ctx, "BACKEND_GENERATION")
    assert recovery.check_circuit_breaker(str(wf_id), "BACKEND_GENERATION", ctx) is True

def test_approval_handler(sync_db):
    """
    ApprovalHandler request trigger, decision processes, and time check triggers.
    """
    db_url = "sqlite://"
    pub = KafkaEventPublisher(bootstrap_servers="localhost:9999")
    handler = ApprovalHandler(db_url=db_url, event_pub=pub, timeout_hours=1)
    handler.SessionLocal = lambda: sync_db

    # Base models setup
    user = User(username="appuser", email="app@test.com", password_hash="pass", role="developer")
    sync_db.add(user)
    sync_db.commit()

    project = Project(user_id=user.user_id, name="AppProj", tech_stack={})
    sync_db.add(project)
    sync_db.commit()

    wf_id = uuid.uuid4()
    workflow = Workflow(workflow_id=wf_id, project_id=project.project_id, current_state="PLANNING")
    sync_db.add(workflow)
    sync_db.commit()

    user_id_str = str(user.user_id)

    # Request approval
    approval_id = handler.request_approval(str(wf_id), "Architecture", {"specs": "details"})
    assert approval_id is not None

    # Decision approval step
    res = handler.process_decision(approval_id, "APPROVED", "looks good", user_id_str)
    assert res["success"] is True
    assert res["next_state"] == "DATABASE_DESIGN"

    # Timeout validation: create expired pending approval
    expired_approval = Approval(
        approval_id=uuid.uuid4(),
        workflow_id=wf_id,
        approval_type="Security",
        status="PENDING",
        artifact_payload={},
        created_at=datetime.utcnow() - timedelta(hours=2)
    )
    sync_db.add(expired_approval)
    sync_db.commit()

    timed_out = handler.check_timeouts()
    assert timed_out == 1
    
    # Reload and verify expired status is REJECTED
    sync_db.refresh(expired_approval)
    assert expired_approval.status == "REJECTED"

def test_base_agent_runtime():
    """
    BaseAgentRuntime capabilities and transition states.
    """
    runtime = BaseAgentRuntime("test-agent")
    assert runtime.agent_id == "test-agent"
    
    res = runtime.execute("test task description")
    assert res["status"] == "COMPLETED"
    
    assert runtime.pause("wf-1") is True
    assert runtime.execution_states["wf-1"] == "PAUSED"
    
    assert runtime.resume("wf-1") is True
    assert runtime.execution_states["wf-1"] == "RUNNING"
    
    assert runtime.cancel("wf-1") is True
    assert runtime.execution_states["wf-1"] == "CANCELLED"

def test_workflow_manager_telemetry(sync_db):
    """
    WorkflowManager integration execution step verification.
    """
    db_url = "sqlite://"
    pub = KafkaEventPublisher(bootstrap_servers="localhost:9999")
    manager = WorkflowManager(db_url=db_url, redis_url="redis://localhost:6379/9", event_pub=pub)
    
    # Re-route sub-components to use local mock db fixture
    manager.checkpoint_mgr.SessionLocal = lambda: sync_db
    manager.approval_handler.SessionLocal = lambda: sync_db
    manager.recovery_mgr.SessionLocal = lambda: sync_db

    # Create base database rows
    user = User(username="mgruser", email="mgr@test.com", password_hash="pass", role="developer")
    sync_db.add(user)
    sync_db.commit()

    project = Project(user_id=user.user_id, name="MgrProj", tech_stack={})
    sync_db.add(project)
    sync_db.commit()

    wf_id = uuid.uuid4()
    workflow = Workflow(workflow_id=wf_id, project_id=project.project_id, current_state="CREATED")
    sync_db.add(workflow)
    sync_db.commit()

    # Executing workflow transitions
    res = manager.start_workflow(str(wf_id), str(project.project_id), "create oauth layer")
    assert res["current_state"] == "DATABASE_DESIGN"

    # Complete database design
    res = manager.on_database_design_completed(str(wf_id), "db-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "BACKEND_GENERATION"

    # Complete backend generation
    res = manager.on_backend_generation_completed(str(wf_id), "be-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "FRONTEND_GENERATION"

    # Complete frontend generation
    res = manager.on_frontend_generation_completed(str(wf_id), "fe-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "TESTING"

    # Complete QA testing
    res = manager.on_qa_generation_completed(str(wf_id), "qa-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "SECURITY_REVIEW"

    # Complete security review
    res = manager.on_security_generation_completed(str(wf_id), "sec-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "DEVOPS_GENERATION"

    # Complete DevOps generation -> triggers APPROVAL_PENDING
    res = manager.on_devops_generation_completed(str(wf_id), "devops-123")
    assert res is True
    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(wf_id))
    assert checkpoint.get("current_node") == "APPROVAL_PENDING"
