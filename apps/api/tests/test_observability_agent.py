import os
import sys
import uuid
import pytest
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
    ObservabilityGeneration,
    AgentMetric,
    WorkflowMetric,
    ApiMetric,
    SystemMetric,
    ErrorEvent,
    AlertRule,
    AlertEvent,
)
from app.repositories.observability import (
    ObservabilityGenerationRepository,
    AgentMetricRepository,
    WorkflowMetricRepository,
    ApiMetricRepository,
    SystemMetricRepository,
    ErrorEventRepository,
    AlertRuleRepository,
    AlertEventRepository,
)
from app.schemas.observability import (
    ObservabilityGenerationPayload,
    AgentMetricPayload,
    WorkflowMetricPayload,
    ApiMetricPayload,
    SystemMetricPayload,
    ErrorEventPayload,
    AlertRulePayload,
    AlertEventPayload,
)
from app.services.observability import ObservabilityService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_payload(
    project_id=None,
    workflow_id=None,
    agent_metrics=None,
    workflow_metrics=None,
    api_metrics=None,
    system_metrics=None,
    error_events=None,
    alert_rules=None,
    alert_events=None,
) -> ObservabilityGenerationPayload:
    return ObservabilityGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        notes="Test observability snapshot",
        agent_metrics=agent_metrics or [
            AgentMetricPayload(
                agent_name="DatabaseAgent",
                duration_ms=1200.0,
                tokens_used=800,
                success_rate=0.98,
                error_count=0,
            )
        ],
        workflow_metrics=workflow_metrics or [
            WorkflowMetricPayload(
                step_name="DATABASE_GENERATION",
                duration_ms=2000.0,
                status="COMPLETED",
                throughput_rps=12.5,
            )
        ],
        api_metrics=api_metrics or [
            ApiMetricPayload(
                endpoint="/api/v1/database/generate",
                method="POST",
                avg_latency_ms=45.0,
                p99_latency_ms=120.0,
                error_rate=0.01,
                request_count=100,
            )
        ],
        system_metrics=system_metrics or [
            SystemMetricPayload(
                service_name="api-gateway",
                cpu_pct=35.0,
                memory_pct=55.0,
                disk_pct=42.0,
            )
        ],
        error_events=error_events or [
            ErrorEventPayload(
                source="api-gateway",
                severity="WARNING",
                message="datetime.utcnow() deprecated",
            )
        ],
        alert_rules=alert_rules or [
            AlertRulePayload(
                rule_name="HighAgentDurationAlert",
                metric_name="duration_ms",
                operator="gt",
                threshold=5000.0,
                severity="WARNING",
            )
        ],
        alert_events=alert_events or [
            AlertEventPayload(
                rule_name="HighAgentDurationAlert",
                current_value=3540.0,
                threshold=5000.0,
                severity="WARNING",
                message="Within bounds",
                status="RESOLVED",
            )
        ],
    )


def _make_svc(db: AsyncSession) -> ObservabilityService:
    return ObservabilityService(
        generation_repo=ObservabilityGenerationRepository(db),
        agent_metric_repo=AgentMetricRepository(db),
        workflow_metric_repo=WorkflowMetricRepository(db),
        api_metric_repo=ApiMetricRepository(db),
        system_metric_repo=SystemMetricRepository(db),
        error_event_repo=ErrorEventRepository(db),
        alert_rule_repo=AlertRuleRepository(db),
        alert_event_repo=AlertEventRepository(db),
        db=db,
    )


# ── 1. TestObservabilityGenerationCreation ────────────────────────────────────

class TestObservabilityGenerationCreation:

    @pytest.mark.asyncio
    async def test_create_generation_persists_root_record(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        assert gen.generation_id is not None
        assert gen.project_id == payload.project_id
        assert gen.workflow_id == payload.workflow_id
        assert gen.status == "COMPLETED"
        assert gen.notes == "Test observability snapshot"

    @pytest.mark.asyncio
    async def test_create_generation_persists_all_child_types(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        agent_metrics = await svc.list_agent_metrics(gen.generation_id)
        workflow_metrics = await svc.list_workflow_metrics(gen.generation_id)
        api_metrics = await svc.list_api_metrics(gen.generation_id)
        system_metrics = await svc.list_system_metrics(gen.generation_id)
        error_events = await svc.list_error_events(gen.generation_id)
        alert_rules = await svc.list_alert_rules(gen.generation_id)
        alert_events = await svc.list_alert_events(gen.generation_id)

        assert len(agent_metrics) == 1
        assert len(workflow_metrics) == 1
        assert len(api_metrics) == 1
        assert len(system_metrics) == 1
        assert len(error_events) == 1
        assert len(alert_rules) == 1
        assert len(alert_events) == 1

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


# ── 2. TestKafkaEventPublishing ───────────────────────────────────────────────

class TestKafkaEventPublishing:

    @pytest.mark.asyncio
    async def test_completion_event_published_on_create(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.observability._kafka_available", True), \
             patch("app.services.observability.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "observability.generation.events"
        assert event["event_type"] == "observability.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_started_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.observability._kafka_available", True), \
             patch("app.services.observability.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "observability.started"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.observability._kafka_available", True), \
             patch("app.services.observability.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="Refresh metrics snapshot",
            )

        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "observability.started"


# ── 3. TestAPIEndpoints ───────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/observability/generate",
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
            f"/api/v1/observability/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_agent_metric_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/observability/agent-metrics/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_error_event_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/observability/error-events/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_alert_rule_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/observability/alert-rules/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ── 4. TestObservabilityAgentTools ────────────────────────────────────────────

class TestObservabilityAgentTools:

    def test_metrics_collector_tool_produces_data(self):
        from agent import metrics_collector_tool
        result = metrics_collector_tool(
            agent_name="DatabaseAgent",
            duration_ms=1200.5,
            tokens_used=800,
            success_rate=0.98,
            error_count=0,
        )
        assert result["agent_name"] == "DatabaseAgent"
        assert result["duration_ms"] == 1200.5
        assert result["tokens_used"] == 800
        assert result["success_rate"] == 0.98
        assert "extra_metadata" in result

    def test_trace_generator_tool_produces_data(self):
        from agent import trace_generator_tool
        wf_id = str(uuid.uuid4())
        result = trace_generator_tool(
            workflow_id=wf_id,
            step_name="DATABASE_GENERATION",
            duration_ms=2000.0,
            status="COMPLETED",
            throughput_rps=12.5,
        )
        assert result["workflow_id"] == wf_id
        assert result["step_name"] == "DATABASE_GENERATION"
        assert result["status"] == "COMPLETED"
        assert result["throughput_rps"] == 12.5

    def test_alert_generator_tool_resolved_when_within_bounds(self):
        from agent import alert_generator_tool
        result = alert_generator_tool(
            rule_name="HighDuration",
            threshold=5000.0,
            current_value=3540.0,
            severity="WARNING",
        )
        assert result["rule_name"] == "HighDuration"
        assert result["status"] == "RESOLVED"
        assert "within bounds" in result["message"]

    def test_alert_generator_tool_open_when_breached(self):
        from agent import alert_generator_tool
        result = alert_generator_tool(
            rule_name="HighMemory",
            threshold=80.0,
            current_value=95.0,
            severity="CRITICAL",
        )
        assert result["status"] == "OPEN"
        assert "exceeds" in result["message"]

    def test_dashboard_generator_tool_produces_panels(self):
        from agent import observability_dashboard_generator_tool
        metrics = [{"duration_ms": 1200.0}, {"duration_ms": 1800.0}]
        result = observability_dashboard_generator_tool("CodeForge Overview", metrics)
        assert result["title"] == "CodeForge Overview"
        assert result["metric_count"] == 2
        assert result["avg_duration_ms"] == 1500.0
        assert len(result["panels"]) == 4
        assert result["generated"] is True

    def test_log_analysis_tool_produces_error_event(self):
        from agent import log_analysis_tool
        result = log_analysis_tool(
            log_text="Connection refused to Kafka broker",
            level="ERROR",
            source="agent-orchestrator",
        )
        assert result["source"] == "agent-orchestrator"
        assert result["severity"] == "ERROR"
        assert "Connection refused" in result["message"]
        assert result["context"] is not None

    def test_health_monitor_tool_produces_data(self):
        from agent import health_monitor_tool
        result = health_monitor_tool(
            service_name="api-gateway",
            cpu_pct=35.5,
            mem_pct=62.0,
            disk_pct=41.0,
        )
        assert result["service_name"] == "api-gateway"
        assert result["cpu_pct"] == 35.5
        assert result["memory_pct"] == 62.0
        assert result["disk_pct"] == 41.0


# ── 5. TestObservabilityAgentExecute ─────────────────────────────────────────

class TestObservabilityAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import ObservabilityAgent
        agent = ObservabilityAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "agent_metrics" in result
        assert "workflow_metrics" in result
        assert "api_metrics" in result
        assert "system_metrics" in result
        assert "error_events" in result
        assert "alert_rules" in result
        assert "alert_events" in result
        assert len(result["agent_metrics"]) == 7   # one per agent
        assert len(result["workflow_metrics"]) == 7  # one per SDLC step
        assert len(result["api_metrics"]) == 8
        assert len(result["system_metrics"]) == 3   # 3 services
        assert len(result["error_events"]) == 2
        assert len(result["alert_rules"]) == 2
        assert len(result["alert_events"]) == 2


# ── 6. TestWorkflowManagerGate ────────────────────────────────────────────────

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

    def test_on_observability_completed_resumes_workflow(self):
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

        result = mgr.on_observability_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"agent_count": 7, "alert_count": 2},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

        # Verify observability.review.requested was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "observability.review.requested" in published_topics

    def test_on_observability_completed_ignores_non_paused(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "RUNNING"

        result = mgr.on_observability_completed(
            workflow_id=wf_id,
            generation_id=str(uuid.uuid4()),
            result_summary={},
        )
        assert result is False

    def test_on_observability_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_observability_failed(
            workflow_id=wf_id,
            error="Metrics collection timed out",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
