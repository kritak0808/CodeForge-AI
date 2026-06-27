import os
import sys
import uuid
import pytest
import importlib.util
from unittest.mock import MagicMock, patch, AsyncMock, ANY
from sqlalchemy.ext.asyncio import AsyncSession

# Setup path resolution for apps/agent-orchestrator and apps/agent-workers
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
workers_path = os.path.join(workspace_root, "apps", "agent-workers")
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)
if workers_path not in sys.path:
    sys.path.insert(0, workers_path)

# Dynamically import agent-workers main.py as a separate module
if "agent_workers_main" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "agent_workers_main",
        os.path.join(workers_path, "main.py")
    )
    agent_workers_main = importlib.util.module_from_spec(spec)
    sys.modules["agent_workers_main"] = agent_workers_main
    spec.loader.exec_module(agent_workers_main)
else:
    agent_workers_main = sys.modules["agent_workers_main"]

from main import app
from app.dependencies import get_current_user, get_autonomous_controller_service
from app.schemas.token import TokenData

from app.models import (
    AutonomousController,
    WorkflowDecision,
    AgentHealth,
    RetryHistory,
    FailureEvent,
    RollbackEvent,
    ExecutionPlan,
    ControllerLog,
)
from app.repositories.controller import (
    AutonomousControllerRepository,
    WorkflowDecisionRepository,
    AgentHealthRepository,
    RetryHistoryRepository,
    FailureEventRepository,
    RollbackEventRepository,
    ExecutionPlanRepository,
    ControllerLogRepository,
)
from app.schemas.controller import (
    AutonomousControllerPayload,
    WorkflowDecisionPayload,
    AgentHealthPayload,
    RetryHistoryPayload,
    FailureEventPayload,
    RollbackEventPayload,
    ExecutionPlanPayload,
    ControllerLogPayload,
)
from app.services.controller import AutonomousControllerService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_payload(
    project_id=None,
    workflow_id=None,
    status="ACTIVE",
    current_step="AUTONOMOUS_CONTROLLER",
    budget_limit=1000.0,
    decisions=None,
    retries=None,
    failures=None,
    rollbacks=None,
    execution_plans=None,
    logs=None,
) -> AutonomousControllerPayload:
    return AutonomousControllerPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        status=status,
        current_step=current_step,
        budget_limit=budget_limit,
        decisions=decisions or [
            WorkflowDecisionPayload(step="AUTONOMOUS_CONTROLLER", decision_type="ROUTE", reason="Path clear", action_taken="PROCEED")
        ],
        retries=retries or [
            RetryHistoryPayload(step="TESTING", retry_attempt=1, max_retries=3, error_message="Transient error")
        ],
        failures=failures or [
            FailureEventPayload(step="TESTING", error_type="COMPILATION_ERROR", error_message="Syntax error")
        ],
        rollbacks=rollbacks or [
            RollbackEventPayload(source_step="TESTING", target_step="BACKEND_GENERATION", reason="QA failures")
        ],
        execution_plans=execution_plans or [
            ExecutionPlanPayload(steps_json=["PLANNING", "RESEARCHING", "FINAL_DEPLOYMENT"], current_step_index=1, is_optimized=True)
        ],
        logs=logs or [
            ControllerLogPayload(level="INFO", message="Autonomous check started")
        ]
    )


def _make_svc(db: AsyncSession) -> AutonomousControllerService:
    return AutonomousControllerService(
        controller_repo=AutonomousControllerRepository(db),
        decision_repo=WorkflowDecisionRepository(db),
        health_repo=AgentHealthRepository(db),
        retry_repo=RetryHistoryRepository(db),
        failure_repo=FailureEventRepository(db),
        rollback_repo=RollbackEventRepository(db),
        plan_repo=ExecutionPlanRepository(db),
        log_repo=ControllerLogRepository(db),
        db=db,
    )


# ── 1. TestControllerPersistence ──────────────────────────────────────────────

class TestControllerPersistence:

    @pytest.mark.asyncio
    async def test_create_controller_from_payload(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        project_id = uuid.uuid4()
        workflow_id = uuid.uuid4()
        payload = _make_payload(project_id=project_id, workflow_id=workflow_id)

        # Call service persistence method
        ctrl = await svc.create_controller_from_payload(payload)

        # Assertions
        assert ctrl.controller_id is not None
        assert ctrl.project_id == project_id
        assert ctrl.workflow_id == workflow_id
        assert ctrl.status == "ACTIVE"
        assert ctrl.current_step == "AUTONOMOUS_CONTROLLER"

        # Check subcomponents
        decisions = await svc.list_decisions(ctrl.controller_id)
        assert len(decisions) == 1
        assert decisions[0].step == "AUTONOMOUS_CONTROLLER"
        assert decisions[0].decision_type == "ROUTE"

        retries = await svc.list_retries(ctrl.controller_id)
        assert len(retries) == 1
        assert retries[0].step == "TESTING"
        assert retries[0].retry_attempt == 1

        failures = await svc.list_failures(ctrl.controller_id)
        assert len(failures) == 1
        assert failures[0].error_message == "Syntax error"

        rollbacks = await svc.list_rollbacks(ctrl.controller_id)
        assert len(rollbacks) == 1
        assert rollbacks[0].target_step == "BACKEND_GENERATION"

        plan = await svc.get_plan(ctrl.controller_id)
        assert plan is not None
        assert plan.is_optimized is True

        logs = await svc.list_logs(ctrl.controller_id)
        assert len(logs) == 1
        assert logs[0].message == "Autonomous check started"


# ── 2. TestRESTControllerEndpoints ────────────────────────────────────────────

from fastapi.testclient import TestClient

class TestRESTControllerEndpoints:

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        # Override the dependency for get_current_user
        mock_user = TokenData(username="admin", scopes=["enterprise"])
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides.clear()

    def test_rest_start(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        app.dependency_overrides[get_autonomous_controller_service] = lambda: svc
        client = TestClient(app)

        payload = {
            "project_id": str(uuid.uuid4()),
            "workflow_id": str(uuid.uuid4())
        }
        res = client.post("/api/v1/controller/start", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["success"] is True
        assert data["data"]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_rest_pause_resume_cancel(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        app.dependency_overrides[get_autonomous_controller_service] = lambda: svc
        client = TestClient(app)

        workflow_id = uuid.uuid4()
        project_id = uuid.uuid4()

        # Create controller first
        payload = _make_payload(project_id=project_id, workflow_id=workflow_id, status="ACTIVE")
        await svc.create_controller_from_payload(payload)

        # Pause
        res = client.post("/api/v1/controller/pause", json={"workflow_id": str(workflow_id)})
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "PAUSED"

        # Resume
        res = client.post("/api/v1/controller/resume", json={"workflow_id": str(workflow_id)})
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "ACTIVE"

        # Cancel
        res = client.post("/api/v1/controller/cancel", json={"workflow_id": str(workflow_id)})
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_rest_retry_rollback(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        app.dependency_overrides[get_autonomous_controller_service] = lambda: svc
        client = TestClient(app)

        workflow_id = uuid.uuid4()
        project_id = uuid.uuid4()
        payload = _make_payload(project_id=project_id, workflow_id=workflow_id)
        
        await svc.create_controller_from_payload(payload)

        # Retry step
        res = client.post("/api/v1/controller/retry", json={"workflow_id": str(workflow_id), "step": "TESTING"})
        assert res.status_code == 200
        assert res.json()["data"]["action"] == "RETRY"

        # Rollback step
        res = client.post("/api/v1/controller/rollback", json={"workflow_id": str(workflow_id), "target_step": "DATABASE_DESIGN", "reason": "failure"})
        assert res.status_code == 200
        assert res.json()["data"]["action"] == "ROLLBACK"

    @pytest.mark.asyncio
    async def test_rest_get_status_and_health(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        app.dependency_overrides[get_autonomous_controller_service] = lambda: svc
        client = TestClient(app)

        workflow_id = uuid.uuid4()
        project_id = uuid.uuid4()
        payload = _make_payload(project_id=project_id, workflow_id=workflow_id)
        
        await svc.create_controller_from_payload(payload)

        # Get status
        res = client.get(f"/api/v1/controller/status/{workflow_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["workflow_id"] == str(workflow_id)
        assert len(data["decisions"]) == 1

        # Get decisions
        res = client.get(f"/api/v1/controller/decisions/{workflow_id}")
        assert res.status_code == 200
        assert len(res.json()) == 1

        # Get health
        res = client.get("/api/v1/controller/health")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ── 3. TestAgentAndWorkers ────────────────────────────────────────────────────

class TestAgentAndWorkers:

    def test_autonomous_controller_agent_execution(self):
        from agent import agent_registry
        agent = agent_registry.get_agent("AutonomousControllerAgent")
        assert agent is not None

        # Clean run scenario
        payload = {
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "current_step": "AUTONOMOUS_CONTROLLER",
            "errors": [],
            "metrics": {},
            "budget_limit": 1000.0,
            "accumulated_cost": 50.0,
            "retry_attempt": 1,
            "agent_heartbeats": {"ResearchAgent": "OK", "DatabaseAgent": "DEGRADED"}
        }
        res = agent.execute(payload)
        assert res["decision"]["decision_type"] == "ROUTE"
        assert res["decision"]["action"] == "MOVE_TO_FINAL_DEPLOYMENT"
        assert len(res["agent_healths"]) == 2
        assert any(h["agent_id"] == "DatabaseAgent" and h["status"] == "DEGRADED" for h in res["agent_healths"])

        # Failure/Retry scenario
        payload_fail = {**payload, "errors": ["QA test timeout"]}
        res_fail = agent.execute(payload_fail)
        assert res_fail["decision"]["decision_type"] == "RETRY"
        assert "RETRY_AUTONOMOUS_CONTROLLER_ATTEMPT_1" in res_fail["decision"]["action"]

        # Failure/Rollback scenario (exceeded retries)
        payload_rollback = {**payload, "errors": ["QA test timeout"], "retry_attempt": 4}
        res_rollback = agent.execute(payload_rollback)
        assert res_rollback["decision"]["decision_type"] == "ROLLBACK"
        assert "ROLLBACK_TO_" in res_rollback["decision"]["action"]

    @patch("agent_workers_main._publish")
    def test_handle_controller_started_worker(self, mock_publish, db_session: AsyncSession):
        # Trigger worker message consumption manually
        workflow_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        message = {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "current_step": "AUTONOMOUS_CONTROLLER",
            "errors": [],
            "metrics": {},
            "budget_limit": 1000.0,
            "accumulated_cost": 50.0,
            "retry_attempt": 1,
            "agent_heartbeats": {"ResearchAgent": "OK"}
        }

        # Mock the AsyncSessionLocal to use our test db session
        from unittest.mock import patch
        with patch("agent_workers_main.AsyncSessionLocal", return_value=db_session):
            agent_workers_main.handle_controller_started(message)

        # Verify Kafka events published
        mock_publish.assert_any_call("controller.completed", ANY)


# ── 4. TestWorkflowManagerControllerIntegration ───────────────────────────────

class TestWorkflowManagerControllerIntegration:

    @patch("workflow_manager.KafkaEventPublisher")
    def test_manager_gating_and_callbacks(self, mock_kafka_publisher, db_session: AsyncSession):
        from workflow_manager import WorkflowManager
        event_pub = mock_kafka_publisher()
        manager = WorkflowManager(db_url="sqlite:///:memory:", redis_url="redis://localhost", event_pub=event_pub)

        workflow_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())

        # Set workflow status to PAUSED in active executions map to mock gating
        manager.active_executions[workflow_id] = "PAUSED"

        # Mock CheckpointManager to return valid context
        manager.checkpoint_mgr = MagicMock()
        manager.checkpoint_mgr.restore_checkpoint.return_value = {
            "current_node": "AUTONOMOUS_CONTROLLER",
            "execution_context": {
                "project_id": project_id
            },
            "agent_outputs": {},
            "errors": []
        }

        # Mock run_workflow_step to not execute full langgraph during callbacks
        with patch.object(manager, "run_workflow_step") as mock_run:
            # 1. Test controller completed callback
            res = manager.on_controller_completed(workflow_id, str(uuid.uuid4()))
            assert res is True
            assert manager.active_executions[workflow_id] == "RUNNING"
            mock_run.assert_called_once()

            # Reset PAUSED
            manager.active_executions[workflow_id] = "PAUSED"
            mock_run.reset_mock()

            # 2. Test controller retry callback
            res_retry = manager.on_controller_retry(workflow_id, str(uuid.uuid4()), "TESTING", 2)
            assert res_retry is True
            assert manager.active_executions[workflow_id] == "RUNNING"
            mock_run.assert_called_once()

            # Reset PAUSED
            manager.active_executions[workflow_id] = "PAUSED"
            mock_run.reset_mock()

            # 3. Test controller rollback callback
            res_rollback = manager.on_controller_rollback(workflow_id, str(uuid.uuid4()), "TESTING", "DATABASE_DESIGN")
            assert res_rollback is True
            assert manager.active_executions[workflow_id] == "RUNNING"
            mock_run.assert_called_once()

            # Reset PAUSED
            manager.active_executions[workflow_id] = "PAUSED"
            mock_run.reset_mock()

            # 4. Test controller failed callback
            res_failed = manager.on_controller_failed(workflow_id, "Critical SDLC orchestrator error")
            assert res_failed is True
            assert manager.active_executions[workflow_id] == "FAILED"
