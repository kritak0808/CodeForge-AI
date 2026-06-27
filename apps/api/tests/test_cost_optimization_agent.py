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

# Dynamically import agent-workers main.py as a separate module to prevent collision with apps/api/main.py
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
from app.dependencies import get_current_user, get_cost_optimization_service
from app.schemas.token import TokenData


from app.models import (
    CostGeneration,
    CostReport,
    ResourceUsageMetric,
    OptimizationRecommendation,
    SavingsEstimate,
    BudgetPolicy,
    CostAlert,
)
from app.repositories.cost import (
    CostGenerationRepository,
    CostReportRepository,
    ResourceUsageMetricRepository,
    OptimizationRecommendationRepository,
    SavingsEstimateRepository,
    BudgetPolicyRepository,
    CostAlertRepository,
)
from app.schemas.cost import (
    CostGenerationPayload,
    CostReportPayload,
    ResourceUsageMetricPayload,
    OptimizationRecommendationPayload,
    SavingsEstimatePayload,
    CostAlertPayload,
    BudgetPolicyRequest,
)
from app.services.cost import CostOptimizationService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_payload(
    project_id=None,
    workflow_id=None,
    total_cost=340.5,
    estimated_monthly_cost=4200.0,
    cost_reports=None,
    resource_usage_metrics=None,
    optimization_recommendations=None,
    savings_estimates=None,
    cost_alerts=None,
) -> CostGenerationPayload:
    return CostGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        total_cost=total_cost,
        estimated_monthly_cost=estimated_monthly_cost,
        currency="USD",
        cost_reports=cost_reports or [
            CostReportPayload(category="LLM_TOKENS", current_cost=140.5, projected_cost=1500.0, notes="Tokens test"),
            CostReportPayload(category="KUBERNETES", current_cost=200.0, projected_cost=2700.0, notes="K8s test"),
        ],
        resource_usage_metrics=resource_usage_metrics or [
            ResourceUsageMetricPayload(resource_type="CPU", utilization_percent=15.0, consumption=4.0, unit="cores"),
            ResourceUsageMetricPayload(resource_type="TOKENS", utilization_percent=95.0, consumption=3000000.0, unit="tokens"),
        ],
        optimization_recommendations=optimization_recommendations or [
            OptimizationRecommendationPayload(title="Downsize Kubernetes clusters", description="Low CPU usage", impact_level="HIGH", estimated_savings=75.0, category="KUBERNETES"),
        ],
        savings_estimates=savings_estimates or [
            SavingsEstimatePayload(monthly_savings=75.0, annual_savings=900.0, confidence_level="HIGH", assumptions="None"),
        ],
        cost_alerts=cost_alerts or [
            CostAlertPayload(severity="WARNING", message="Nearing threshold", current_cost=4200.0, budget_limit=5000.0, status="OPEN"),
        ]
    )


def _make_svc(db: AsyncSession) -> CostOptimizationService:
    return CostOptimizationService(
        generation_repo=CostGenerationRepository(db),
        report_repo=CostReportRepository(db),
        metric_repo=ResourceUsageMetricRepository(db),
        recommendation_repo=OptimizationRecommendationRepository(db),
        savings_repo=SavingsEstimateRepository(db),
        policy_repo=BudgetPolicyRepository(db),
        alert_repo=CostAlertRepository(db),
        db=db,
    )


# ── 1. TestCostGenerationCreation ─────────────────────────────────────────────

class TestCostGenerationCreation:

    @pytest.mark.asyncio
    async def test_create_cost_generation_from_payload(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        project_id = uuid.uuid4()
        workflow_id = uuid.uuid4()
        payload = _make_payload(project_id=project_id, workflow_id=workflow_id)

        # Call service persistence method
        gen = await svc.create_generation_from_payload(payload)

        # Assertions
        assert gen.generation_id is not None
        assert gen.project_id == project_id
        assert gen.workflow_id == workflow_id
        assert gen.status == "COMPLETED"
        assert gen.total_cost == 340.5
        assert gen.estimated_monthly_cost == 4200.0

        # Retrieve and verify children
        reports = await svc.list_reports(gen.generation_id)
        assert len(reports) == 2
        assert {r.category for r in reports} == {"LLM_TOKENS", "KUBERNETES"}

        metrics = await svc.list_metrics(gen.generation_id)
        assert len(metrics) == 2
        assert {m.resource_type for m in metrics} == {"CPU", "TOKENS"}

        recs = await svc.list_recommendations(gen.generation_id)
        assert len(recs) == 1
        assert recs[0].title == "Downsize Kubernetes clusters"

        savings = await svc.list_savings(gen.generation_id)
        assert len(savings) == 1
        assert savings[0].monthly_savings == 75.0

        alerts = await svc.list_alerts(gen.generation_id)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"


# ── 2. TestCostAgentTools ─────────────────────────────────────────────────────

class TestCostAgentTools:

    def test_token_cost_analyzer_tool(self):
        from agent import token_cost_analyzer_tool
        # Case: GPT-4o
        res = token_cost_analyzer_tool(1_000_000, 1_000_000, "gpt-4o")
        assert res["category"] == "LLM_TOKENS"
        assert res["current_cost"] == 5.0 + 15.0

        # Case: Claude
        res = token_cost_analyzer_tool(1_000_000, 1_000_000, "claude-3-5-sonnet")
        assert res["current_cost"] == 3.0 + 15.0

    def test_resource_cost_analyzer_tool(self):
        from agent import resource_cost_analyzer_tool
        res = resource_cost_analyzer_tool(2.0, 8.0, 10.0)
        assert res["category"] == "KUBERNETES"
        # Cost = (2.0 * 0.04 + 8.0 * 0.005) * 10.0 = (0.08 + 0.04) * 10.0 = 1.20
        assert res["current_cost"] == 1.20

    def test_storage_cost_tool(self):
        from agent import storage_cost_tool
        res = storage_cost_tool(100.0, 1_000_000, 4.0)
        assert res["category"] == "POSTGRESQL"
        assert res["projected_cost"] > 0

    def test_budget_monitor_tool(self):
        from agent import budget_monitor_tool
        # Under limit
        alerts = budget_monitor_tool("project-123", 100.0, 500.0, 0.8)
        assert len(alerts) == 0

        # Warning
        alerts = budget_monitor_tool("project-123", 410.0, 500.0, 0.8)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "WARNING"

        # Critical
        alerts = budget_monitor_tool("project-123", 510.0, 500.0, 0.8)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "CRITICAL"

    def test_optimization_recommender_tool(self):
        from agent import optimization_recommender_tool
        res = optimization_recommender_tool("CPU", 15.0)
        assert res["impact_level"] == "HIGH"
        assert "Downsize" in res["title"]

        res = optimization_recommender_tool("TOKENS", 85.0)
        assert res["impact_level"] == "MEDIUM"
        assert "caching" in res["title"]

    def test_savings_estimator_tool(self):
        from agent import savings_estimator_tool
        res = savings_estimator_tool(500.0, 400.0)
        assert res["monthly_savings"] == 100.0
        assert res["annual_savings"] == 1200.0


# ── 3. TestCostAgentExecute ───────────────────────────────────────────────────

class TestCostAgentExecute:

    def test_cost_agent_execute_produces_payload(self):
        from agent import CostOptimizationAgent
        agent = CostOptimizationAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })

        assert "cost_reports" in result
        assert "resource_usage_metrics" in result
        assert "optimization_recommendations" in result
        assert "savings_estimates" in result
        assert "cost_alerts" in result
        assert result["total_cost"] > 0
        assert result["estimated_monthly_cost"] > 0


# ── 4. TestWorkflowManagerCostGate ────────────────────────────────────────────

class TestWorkflowManagerCostGate:

    def _make_manager(self):
        with patch("workflow_manager.CheckpointManager"), \
             patch("workflow_manager.ApprovalHandler"), \
             patch("workflow_manager.RecoveryManager"), \
             patch("workflow_manager.compile_sdlc_graph") as mock_graph_fn:

            mock_graph_fn.return_value = MagicMock()
            mock_event_pub = MagicMock()

            from workflow_manager import WorkflowManager
            mgr = WorkflowManager(
                db_url="sqlite:///test.db",
                redis_url="redis://localhost:6379",
                event_pub=mock_event_pub,
            )
            mgr._mock_event_pub = mock_event_pub
            return mgr

    def test_on_cost_analysis_completed_resumes_workflow(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {"project_id": str(uuid.uuid4())},
            "agent_outputs": {},
            "errors": [],
        }
        mgr.run_workflow_step = MagicMock(return_value={"status": "RUNNING"})

        result = mgr.on_cost_analysis_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"total_cost": 340.5},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

        # Verify WORKFLOW_RESUMED event was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "workflow.events" in published_topics

    def test_on_cost_analysis_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_cost_analysis_failed(
            workflow_id=wf_id,
            error="Token calculation timeout error",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()


# ── 5. TestRESTCostEndpoints ──────────────────────────────────────────────────

class TestRESTCostEndpoints:

    @pytest.mark.asyncio
    async def test_rest_generate_cost(self, client):
        mock_svc = MagicMock()
        mock_gen = MagicMock(generation_id=uuid.uuid4(), status="PENDING")
        mock_svc.trigger_generation = AsyncMock(return_value=mock_gen)

        payload = {"project_id": str(uuid.uuid4()), "workflow_id": str(uuid.uuid4())}
        headers = {"Authorization": "Bearer test-token"}
        
        app.dependency_overrides[get_current_user] = lambda: TokenData(username="testuser", role="admin", scopes=[])
        app.dependency_overrides[get_cost_optimization_service] = lambda: mock_svc
        try:
            response = await client.post("/api/v1/cost/generate", json=payload, headers=headers)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_cost_optimization_service, None)

        assert response.status_code == 202
        assert response.json()["success"] is True
        assert response.json()["data"]["generation_id"] == str(mock_gen.generation_id)

    @pytest.mark.asyncio
    async def test_rest_get_generation_full(self, client):
        mock_svc = MagicMock()

        gen_id = uuid.uuid4()
        mock_gen = MagicMock(
            generation_id=gen_id,
            project_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            status="COMPLETED",
            total_cost=150.0,
            estimated_monthly_cost=4500.0,
            currency="USD",
            created_at=None,
            updated_at=None,
        )
        mock_svc.get_generation = AsyncMock(return_value=mock_gen)
        mock_svc.list_reports = AsyncMock(return_value=[])
        mock_svc.list_metrics = AsyncMock(return_value=[])
        mock_svc.list_recommendations = AsyncMock(return_value=[])
        mock_svc.list_savings = AsyncMock(return_value=[])
        mock_svc.list_alerts = AsyncMock(return_value=[])

        headers = {"Authorization": "Bearer test-token"}
        app.dependency_overrides[get_current_user] = lambda: TokenData(username="testuser", role="admin", scopes=[])
        app.dependency_overrides[get_cost_optimization_service] = lambda: mock_svc
        try:
            response = await client.get(f"/api/v1/cost/generations/{gen_id}", headers=headers)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_cost_optimization_service, None)

        assert response.status_code == 200
        assert response.json()["generation_id"] == str(gen_id)

    @pytest.mark.asyncio
    async def test_rest_budget_policies(self, client):
        mock_svc = MagicMock()

        policy_id = uuid.uuid4()
        project_id = uuid.uuid4()
        mock_policy = MagicMock(
            policy_id=policy_id,
            project_id=project_id,
            monthly_budget=500.0,
            alert_threshold=0.8,
            currency="USD",
            is_active=True,
            created_at=None,
            updated_at=None,
        )
        mock_svc.upsert_budget_policy = AsyncMock(return_value=mock_policy)
        mock_svc.get_budget_policy = AsyncMock(return_value=mock_policy)

        headers = {"Authorization": "Bearer test-token"}
        app.dependency_overrides[get_current_user] = lambda: TokenData(username="testuser", role="admin", scopes=[])
        app.dependency_overrides[get_cost_optimization_service] = lambda: mock_svc
        try:
            payload = {"project_id": str(project_id), "monthly_budget": 500.0, "alert_threshold": 0.8}
            response = await client.post("/api/v1/cost/budget-policies", json=payload, headers=headers)
            assert response.status_code == 201
            assert response.json()["policy_id"] == str(policy_id)

            response = await client.get(f"/api/v1/cost/budget-policies/{project_id}", headers=headers)
            assert response.status_code == 200
            assert response.json()["project_id"] == str(project_id)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_cost_optimization_service, None)


# ── 6. TestAgentWorkerCostStarted ─────────────────────────────────────────────

class TestAgentWorkerCostStarted:

    @patch("agent_workers_main.BudgetPolicyRepository")
    @patch("agent_workers_main._publish")
    @patch("agent_workers_main.AsyncSessionLocal")
    @patch("agent_workers_main.CostOptimizationService")
    def test_handle_cost_started(self, mock_service_cls, mock_session_maker, mock_pub, mock_policy_repo_cls):
        mock_session = MagicMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_svc = MagicMock()
        mock_service_cls.return_value = mock_svc
        
        mock_gen = MagicMock(generation_id=uuid.uuid4(), status="COMPLETED")
        mock_gen._event_pub = None
        mock_svc.create_generation_from_payload = AsyncMock(return_value=mock_gen)

        mock_policy_repo = MagicMock()
        mock_policy_repo_cls.return_value = mock_policy_repo
        mock_policy_repo.get_by_project = AsyncMock(return_value=None)

        message = {
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
        }
        agent_workers_main.handle_cost_started(message)

        mock_svc.create_generation_from_payload.assert_called_once()
        mock_pub.assert_called_with("cost.generation.events", ANY)
