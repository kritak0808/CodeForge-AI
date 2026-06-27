import os
import sys
import uuid
import pytest
import json
from unittest.mock import MagicMock, patch

# Setup path resolution for apps/agent-orchestrator and apps/agent-workers
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
workers_path = os.path.join(workspace_root, "apps", "agent-workers")
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)
if workers_path not in sys.path:
    sys.path.insert(0, workers_path)

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    QaGeneration,
    QaTestSuite,
    QaTestCase,
    QaTestRun,
    QaBugReport,
    QaCoverageReport,
    QaQualityMetrics,
)
from app.repositories.qa import (
    QaGenerationRepository,
    QaTestSuiteRepository,
    QaTestCaseRepository,
    QaTestRunRepository,
    QaBugReportRepository,
    QaCoverageReportRepository,
    QaQualityMetricsRepository,
)
from app.schemas.qa import (
    QaGenerationPayload,
    QaTestSuitePayload,
    QaTestCasePayload,
    QaTestRunPayload,
    QaBugReportPayload,
    QaCoverageReportPayload,
    QaQualityMetricsPayload,
)
from app.services.qa import QaGenerationService


def _make_payload(
    project_id=None,
    workflow_id=None,
    backend_generation_id=None,
    frontend_generation_id=None,
    design_id=None,
    report_id=None,
    test_suites=None,
    test_cases=None,
    test_runs=None,
    bug_reports=None,
    coverage_reports=None,
    quality_metrics=None,
) -> QaGenerationPayload:
    return QaGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        backend_generation_id=backend_generation_id or uuid.uuid4(),
        frontend_generation_id=frontend_generation_id or uuid.uuid4(),
        design_id=design_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        notes="Test QA generation",
        test_suites=test_suites or [
            QaTestSuitePayload(
                suite_name="test_backend.py",
                suite_type="pytest",
                file_path="tests/test_backend.py",
                code="def test_sample(): assert True",
            )
        ],
        test_cases=test_cases or [
            QaTestCasePayload(
                case_name="test_backend_sample",
                description="Checks sample endpoint flow",
                test_code="def test_sample(): assert True",
            )
        ],
        test_runs=test_runs or [
            QaTestRunPayload(
                runner_name="pytest",
                status="PASSED",
                summary_json={"passed": 1, "failed": 0},
                stdout="1 passed",
                stderr="",
            )
        ],
        bug_reports=bug_reports or [
            QaBugReportPayload(
                title="Sample bug",
                severity="LOW",
                description="Minor visual issue",
                steps_to_reproduce="Steps...",
                expected_behavior="Expected...",
                actual_behavior="Actual...",
                metadata_json={"env": "test"},
            )
        ],
        coverage_reports=coverage_reports or [
            QaCoverageReportPayload(
                coverage_type="backend",
                line_coverage=95.5,
                branch_coverage=90.0,
                summary_json={"covered": 100},
            )
        ],
        quality_metrics=quality_metrics or [
            QaQualityMetricsPayload(
                overall_score=98.0,
                reliability_score=99.0,
                security_score=97.0,
                maintainability_score=98.0,
                details_json={"checks": 10},
            )
        ],
    )


def _make_svc(db: AsyncSession) -> QaGenerationService:
    return QaGenerationService(
        generation_repo=QaGenerationRepository(db),
        suite_repo=QaTestSuiteRepository(db),
        case_repo=QaTestCaseRepository(db),
        run_repo=QaTestRunRepository(db),
        bug_repo=QaBugReportRepository(db),
        coverage_repo=QaCoverageReportRepository(db),
        metrics_repo=QaQualityMetricsRepository(db),
        db=db,
    )


# ────────────────────────────────────────────────────────────────────────────
# 1. TestQaGenerationCreation
# ────────────────────────────────────────────────────────────────────────────

class TestQaGenerationCreation:

    @pytest.mark.asyncio
    async def test_create_generation_persists_root_record(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        assert gen.generation_id is not None
        assert gen.project_id == payload.project_id
        assert gen.workflow_id == payload.workflow_id
        assert gen.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_create_generation_persists_all_child_types(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        suites = await svc.list_test_suites(gen.generation_id)
        cases = await svc.list_test_cases(gen.generation_id)
        runs = await svc.list_test_runs(gen.generation_id)
        bugs = await svc.list_bug_reports(gen.generation_id)
        coverages = await svc.list_coverage_reports(gen.generation_id)
        metrics = await svc.list_quality_metrics(gen.generation_id)

        assert len(suites) == 1
        assert len(cases) == 1
        assert len(runs) == 1
        assert len(bugs) == 1
        assert len(coverages) == 1
        assert len(metrics) == 1

    @pytest.mark.asyncio
    async def test_trigger_generation_creates_pending_record(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        project_id = uuid.uuid4()
        workflow_id = uuid.uuid4()

        gen = await svc.trigger_generation(
            project_id=project_id,
            workflow_id=workflow_id,
        )
        assert gen.status == "PENDING"
        assert gen.project_id == project_id
        assert gen.workflow_id == workflow_id


# ────────────────────────────────────────────────────────────────────────────
# 2. TestKafkaEventPublishing
# ────────────────────────────────────────────────────────────────────────────

class TestKafkaEventPublishing:

    @pytest.mark.asyncio
    async def test_completion_event_published_on_create(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.qa._kafka_available", True), \
             patch("app.services.qa.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "qa.generation.events"
        assert event["event_type"] == "qa.generation.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_requested_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.qa._kafka_available", True), \
             patch("app.services.qa.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "qa.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.qa._kafka_available", True), \
             patch("app.services.qa.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="Recheck database rules",
            )

        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "qa.generation.requested"


# ────────────────────────────────────────────────────────────────────────────
# 3. TestAPIEndpoints
# ────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/qa/generate",
            json={
                "project_id": str(uuid.uuid4()),
                "workflow_id": str(uuid.uuid4()),
            },
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (202, 401, 403, 422)

    @pytest.mark.asyncio
    async def test_get_generation_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/qa/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_test_suite_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/qa/test-suites/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ────────────────────────────────────────────────────────────────────────────
# 4. TestQaAgentTools
# ────────────────────────────────────────────────────────────────────────────

class TestQaAgentTools:

    def test_pytest_generator_tool_produces_code(self):
        from agent import pytest_generator_tool
        result = pytest_generator_tool("Backend", "Backend Unit Tests")
        assert result["suite_name"] == "test_backend.py"
        assert result["suite_type"] == "pytest"
        assert "def test_backend_base_flow" in result["code"]

    def test_playwright_generator_tool_produces_code(self):
        from agent import playwright_generator_tool
        result = playwright_generator_tool("Dashboard", "Verify main widgets paint")
        assert result["suite_name"] == "dashboard.spec.ts"
        assert result["suite_type"] == "playwright"
        assert "verify Dashboard e2e flow" in result["code"]

    def test_integration_test_tool_produces_code(self):
        from agent import integration_test_tool
        result = integration_test_tool("AuthService", "Redis")
        assert "authservice" in result["case_name"].lower()
        assert "integration_authservice_to_redis" in result["test_code"]

    def test_coverage_analyzer_tool_produces_data(self):
        from agent import coverage_analyzer_tool
        result = coverage_analyzer_tool("backend")
        assert result["coverage_type"] == "backend"
        assert result["line_coverage"] == 92.5

    def test_bug_report_tool_produces_data(self):
        from agent import bug_report_tool
        result = bug_report_tool("Telemetry socket timeout", "HIGH", "Fails to connect")
        assert result["title"] == "Telemetry socket timeout"
        assert result["severity"] == "HIGH"
        assert "Fails to connect" in result["description"]

    def test_quality_score_tool_produces_data(self):
        from agent import quality_score_tool
        result = quality_score_tool("overall")
        assert result["overall_score"] == 95.0


# ────────────────────────────────────────────────────────────────────────────
# 5. TestQaAgentExecute
# ────────────────────────────────────────────────────────────────────────────

class TestQaAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import QAAgent
        agent = QAAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "test_suites" in result
        assert "test_cases" in result
        assert "test_runs" in result
        assert "bug_reports" in result
        assert "coverage_reports" in result
        assert "quality_metrics" in result
        assert len(result["test_suites"]) == 2
        assert len(result["test_cases"]) == 2
        assert len(result["test_runs"]) == 2
        assert len(result["coverage_reports"]) == 2


# ────────────────────────────────────────────────────────────────────────────
# 6. TestWorkflowManagerGate
# ────────────────────────────────────────────────────────────────────────────

class TestWorkflowManagerGate:

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

    def test_on_qa_generation_completed_resumes_workflow(self):
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

        result = mgr.on_qa_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"suite_count": 2, "case_count": 2},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

        # Verify qa.review.requested event was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "qa.review.requested" in published_topics

    def test_on_qa_generation_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_qa_generation_failed(
            workflow_id=wf_id,
            error="Test timeout exception",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
