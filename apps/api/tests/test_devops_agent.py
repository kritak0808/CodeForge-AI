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
    DevopsGeneration,
    DockerArtifact,
    KubernetesArtifact,
    HelmArtifact,
    TerraformArtifact,
    CicdPipeline,
    DeploymentTemplate,
)
from app.repositories.devops import (
    DevopsGenerationRepository,
    DockerArtifactRepository,
    KubernetesArtifactRepository,
    HelmArtifactRepository,
    TerraformArtifactRepository,
    CicdPipelineRepository,
    DeploymentTemplateRepository,
)
from app.schemas.devops import (
    DevOpsGenerationPayload,
    DockerArtifactPayload,
    KubernetesArtifactPayload,
    HelmArtifactPayload,
    TerraformArtifactPayload,
    CicdPipelinePayload,
    DeploymentTemplatePayload,
)
from app.services.devops import DevOpsGenerationService


def _make_payload(
    project_id=None,
    workflow_id=None,
    backend_generation_id=None,
    frontend_generation_id=None,
    design_id=None,
    report_id=None,
    docker_artifacts=None,
    kubernetes_artifacts=None,
    helm_artifacts=None,
    terraform_artifacts=None,
    cicd_pipelines=None,
    deployment_templates=None,
) -> DevOpsGenerationPayload:
    return DevOpsGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        backend_generation_id=backend_generation_id or uuid.uuid4(),
        frontend_generation_id=frontend_generation_id or uuid.uuid4(),
        design_id=design_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        notes="Test DevOps config assessment",
        docker_artifacts=docker_artifacts or [
            DockerArtifactPayload(
                file_name="Dockerfile",
                content="FROM python:3.12-slim"
            )
        ],
        kubernetes_artifacts=kubernetes_artifacts or [
            KubernetesArtifactPayload(
                manifest_name="deployment.yaml",
                manifest_type="deployment",
                content="apiVersion: apps/v1"
            )
        ],
        helm_artifacts=helm_artifacts or [
            HelmArtifactPayload(
                file_path="values.yaml",
                content="replicaCount: 3"
            )
        ],
        terraform_artifacts=terraform_artifacts or [
            TerraformArtifactPayload(
                file_path="main.tf",
                content="provider aws {}"
            )
        ],
        cicd_pipelines=cicd_pipelines or [
            CicdPipelinePayload(
                provider="github_actions",
                content="name: CI"
            )
        ],
        deployment_templates=deployment_templates or [
            DeploymentTemplatePayload(
                target_platform="AWS_ECS",
                content="taskDefinition"
            )
        ],
    )


def _make_svc(db: AsyncSession) -> DevOpsGenerationService:
    return DevOpsGenerationService(
        generation_repo=DevopsGenerationRepository(db),
        docker_repo=DockerArtifactRepository(db),
        kubernetes_repo=KubernetesArtifactRepository(db),
        helm_repo=HelmArtifactRepository(db),
        terraform_repo=TerraformArtifactRepository(db),
        pipeline_repo=CicdPipelineRepository(db),
        template_repo=DeploymentTemplateRepository(db),
        db=db,
    )


# ── 1. TestDevopsGenerationCreation ─────────────────────────────────────────

class TestDevopsGenerationCreation:

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

        dockers = await svc.list_docker_artifacts(gen.generation_id)
        k8s = await svc.list_kubernetes_artifacts(gen.generation_id)
        helms = await svc.list_helm_artifacts(gen.generation_id)
        tfs = await svc.list_terraform_artifacts(gen.generation_id)
        pipelines = await svc.list_cicd_pipelines(gen.generation_id)
        templates = await svc.list_deployment_templates(gen.generation_id)

        assert len(dockers) == 1
        assert len(k8s) == 1
        assert len(helms) == 1
        assert len(tfs) == 1
        assert len(pipelines) == 1
        assert len(templates) == 1

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
        with patch("app.services.devops._kafka_available", True), \
             patch("app.services.devops.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "devops.generation.events"
        assert event["event_type"] == "devops.generation.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_requested_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.devops._kafka_available", True), \
             patch("app.services.devops.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "devops.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.devops._kafka_available", True), \
             patch("app.services.devops.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="Rebuild templates",
            )

        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "devops.generation.requested"


# ── 3. TestAPIEndpoints ───────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/devops/generate",
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
            f"/api/v1/devops/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_docker_artifact_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/devops/docker-artifacts/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ── 4. TestDevopsAgentTools ─────────────────────────────────────────────────

class TestDevopsAgentTools:

    def test_docker_generator_tool_produces_data(self):
        from agent import docker_generator_tool
        result = docker_generator_tool("Dockerfile", "FROM python")
        assert result["file_name"] == "Dockerfile"
        assert result["content"] == "FROM python"

    def test_kubernetes_generator_tool_produces_data(self):
        from agent import kubernetes_generator_tool
        result = kubernetes_generator_tool("pod.yaml", "pod", "kind: Pod")
        assert result["manifest_name"] == "pod.yaml"
        assert result["manifest_type"] == "pod"
        assert result["content"] == "kind: Pod"

    def test_helm_generator_tool_produces_data(self):
        from agent import helm_generator_tool
        result = helm_generator_tool("values.yaml", "replicaCount: 2")
        assert result["file_path"] == "values.yaml"
        assert result["content"] == "replicaCount: 2"

    def test_terraform_generator_tool_produces_data(self):
        from agent import terraform_generator_tool
        result = terraform_generator_tool("main.tf", "resource aws")
        assert result["file_path"] == "main.tf"
        assert result["content"] == "resource aws"

    def test_cicd_generator_tool_produces_data(self):
        from agent import cicd_generator_tool
        result = cicd_generator_tool("github_actions", "on: push")
        assert result["provider"] == "github_actions"
        assert result["content"] == "on: push"

    def test_deployment_template_tool_produces_data(self):
        from agent import deployment_template_tool
        result = deployment_template_tool("AWS_ECS", "containerDefinitions")
        assert result["target_platform"] == "AWS_ECS"
        assert result["content"] == "containerDefinitions"


# ── 5. TestDevopsAgentExecute ───────────────────────────────────────────────

class TestDevopsAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import DevOpsAgent
        agent = DevOpsAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "docker_artifacts" in result
        assert "kubernetes_artifacts" in result
        assert "helm_artifacts" in result
        assert "terraform_artifacts" in result
        assert "cicd_pipelines" in result
        assert "deployment_templates" in result
        assert len(result["docker_artifacts"]) == 2
        assert len(result["kubernetes_artifacts"]) == 2
        assert len(result["helm_artifacts"]) == 2
        assert len(result["terraform_artifacts"]) == 2
        assert len(result["cicd_pipelines"]) == 1
        assert len(result["deployment_templates"]) == 1


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

    def test_on_devops_generation_completed_resumes_workflow(self):
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

        result = mgr.on_devops_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"docker_count": 2, "kubernetes_count": 2},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

        # Verify devops.review.requested event was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "devops.review.requested" in published_topics

    def test_on_devops_generation_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_devops_generation_failed(
            workflow_id=wf_id,
            error="Terraform compilation timed out",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
