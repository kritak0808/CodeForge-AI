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
    FrontendGeneration,
    FrontendPage,
    FrontendComponent,
    FrontendForm,
    FrontendHook,
    FrontendTestReport,
    UiDesignArtifact,
)
from app.repositories.frontend import (
    FrontendGenerationRepository,
    FrontendPageRepository,
    FrontendComponentRepository,
    FrontendFormRepository,
    FrontendHookRepository,
    FrontendTestReportRepository,
    UiDesignArtifactRepository,
)
from app.schemas.frontend import (
    FrontendGenerationPayload,
    FrontendPagePayload,
    FrontendComponentPayload,
    FrontendFormPayload,
    FrontendHookPayload,
    FrontendTestReportPayload,
    UiDesignArtifactPayload,
)
from app.services.frontend import FrontendGenerationService


def _make_payload(
    project_id=None,
    workflow_id=None,
    backend_generation_id=None,
    design_id=None,
    report_id=None,
    pages=None,
    components=None,
    forms=None,
    hooks=None,
    test_reports=None,
    ui_design_artifacts=None,
) -> FrontendGenerationPayload:
    return FrontendGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        backend_generation_id=backend_generation_id or uuid.uuid4(),
        design_id=design_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        framework="Next.js 15",
        language="TypeScript",
        notes="Test frontend generation",
        pages=pages or [
            FrontendPagePayload(
                page_type="Dashboard",
                route_path="/dashboard",
                code="export default function Page() { return <div>Dashboard</div> }",
                metadata_json={"layout": "grid"}
            )
        ],
        components=components or [
            FrontendComponentPayload(
                component_name="DataTable",
                component_type="Data Tables",
                code="export function DataTable() { return <table></table> }",
                metadata_json={"type": "table"}
            )
        ],
        forms=forms or [
            FrontendFormPayload(
                form_name="CreateForm",
                fields_schema={"name": "string"},
                validation_schema="z.object({ name: z.string() })",
                code="export function CreateForm() { return <form></form> }"
            )
        ],
        hooks=hooks or [
            FrontendHookPayload(
                hook_name="useFetchWorkflow",
                hook_type="react-query",
                code="export function useFetchWorkflow() { return useQuery(...) }"
            )
        ],
        test_reports=test_reports or [
            FrontendTestReportPayload(
                test_type="Page Generation Tests",
                test_name="test_dashboard_page",
                test_code="describe('Dashboard', () => {})"
            )
        ],
        ui_design_artifacts=ui_design_artifacts or [
            UiDesignArtifactPayload(
                artifact_name="theme.css",
                artifact_type="ColorPalette",
                content=":root { --background: 0 0% 100%; }"
            )
        ]
    )


def _make_svc(db: AsyncSession) -> FrontendGenerationService:
    return FrontendGenerationService(
        generation_repo=FrontendGenerationRepository(db),
        page_repo=FrontendPageRepository(db),
        component_repo=FrontendComponentRepository(db),
        form_repo=FrontendFormRepository(db),
        hook_repo=FrontendHookRepository(db),
        test_repo=FrontendTestReportRepository(db),
        ui_design_artifact_repo=UiDesignArtifactRepository(db),
        db=db,
    )


# ────────────────────────────────────────────────────────────────────────────
# 1. TestFrontendGenerationCreation
# ────────────────────────────────────────────────────────────────────────────

class TestFrontendGenerationCreation:

    @pytest.mark.asyncio
    async def test_create_generation_persists_root_record(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        assert gen.generation_id is not None
        assert gen.project_id == payload.project_id
        assert gen.workflow_id == payload.workflow_id
        assert gen.status == "COMPLETED"
        assert gen.framework == "Next.js 15"
        assert gen.language == "TypeScript"

    @pytest.mark.asyncio
    async def test_create_generation_persists_all_child_types(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        pages = await svc.list_pages(gen.generation_id)
        components = await svc.list_components(gen.generation_id)
        forms = await svc.list_forms(gen.generation_id)
        hooks = await svc.list_hooks(gen.generation_id)
        tests = await svc.list_tests(gen.generation_id)
        artifacts = await svc.list_ui_design_artifacts(gen.generation_id)

        assert len(pages) == 1
        assert len(components) == 1
        assert len(forms) == 1
        assert len(hooks) == 1
        assert len(tests) == 1
        assert len(artifacts) == 1

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
        with patch("app.services.frontend._kafka_available", True), \
             patch("app.services.frontend.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "frontend.generation.completed"
        assert event["event_type"] == "frontend.generation.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_requested_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.frontend._kafka_available", True), \
             patch("app.services.frontend.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "frontend.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.frontend._kafka_available", True), \
             patch("app.services.frontend.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="UI design updated",
            )

        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "frontend.generation.requested"


# ────────────────────────────────────────────────────────────────────────────
# 3. TestAPIEndpoints
# ────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/frontend/generate",
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
            f"/api/v1/frontend/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_page_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/frontend/pages/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ────────────────────────────────────────────────────────────────────────────
# 4. TestFrontendAgentTools
# ────────────────────────────────────────────────────────────────────────────

class TestFrontendAgentTools:

    def test_page_generator_tool_produces_code(self):
        from agent import page_generator_tool
        result = page_generator_tool("Dashboard", "/dashboard")
        assert result["page_type"] == "Dashboard"
        assert result["route_path"] == "/dashboard"
        assert "use client" in result["code"]
        assert "DashboardWorkspace" in result["code"].replace(" ", "")

    def test_component_generator_tool_produces_code(self):
        from agent import component_generator_tool
        result = component_generator_tool("DataTable", "Data Tables")
        assert result["component_name"] == "DataTable"
        assert result["component_type"] == "Data Tables"
        assert "interface DataTableProps" in result["code"]

    def test_form_generator_tool_produces_code(self):
        from agent import form_generator_tool
        result = form_generator_tool("CreateForm")
        assert result["form_name"] == "CreateForm"
        assert "CreateFormSchema" in result["code"]
        assert "CreateFormSchema = z.object" in result["validation_schema"]

    def test_hook_generator_tool_produces_code(self):
        from agent import hook_generator_tool
        result = hook_generator_tool("useFetchWorkflow", "react-query")
        assert result["hook_name"] == "useFetchWorkflow"
        assert "react-query" in result["code"]

    def test_dashboard_generator_tool_produces_code(self):
        from agent import dashboard_generator_tool
        result = dashboard_generator_tool()
        assert result["page_type"] == "Dashboard"
        assert result["route_path"] == "/dashboard"
        assert "DashboardOverview" in result["code"]

    def test_test_generator_tool_produces_code(self):
        from agent import frontend_test_generator_tool
        result = frontend_test_generator_tool("Dashboard", "Page Generation Tests")
        assert result["test_type"] == "Page Generation Tests"
        assert "test_dashboard" in result["test_name"]
        assert "describe(\"Dashboard test suites\"" in result["test_code"]


# ────────────────────────────────────────────────────────────────────────────
# 5. TestFrontendAgentExecute
# ────────────────────────────────────────────────────────────────────────────

class TestFrontendAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import FrontendAgent
        agent = FrontendAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "pages" in result
        assert "components" in result
        assert "forms" in result
        assert "hooks" in result
        assert "test_reports" in result
        assert "ui_design_artifacts" in result
        assert len(result["pages"]) == 8
        assert len(result["components"]) == 7
        assert len(result["forms"]) == 2
        assert len(result["hooks"]) == 3
        assert len(result["test_reports"]) == 8


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

    def test_on_frontend_generation_completed_resumes_workflow(self):
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

        result = mgr.on_frontend_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"page_count": 8, "component_count": 7},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()
        
        # Verify frontend.review.requested event was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "frontend.review.requested" in published_topics

    def test_on_frontend_generation_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_frontend_generation_failed(
            workflow_id=wf_id,
            error="Docker workspace out of disk space",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
