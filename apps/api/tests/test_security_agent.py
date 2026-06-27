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
    SecurityGeneration,
    ThreatModel,
    SecurityFinding,
    DependencyScan,
    SecretScan,
    RbacAudit,
    SecurityReport,
)
from app.repositories.security import (
    SecurityGenerationRepository,
    ThreatModelRepository,
    SecurityFindingRepository,
    DependencyScanRepository,
    SecretScanRepository,
    RbacAuditRepository,
    SecurityReportRepository,
)
from app.schemas.security import (
    SecurityGenerationPayload,
    ThreatModelPayload,
    SecurityFindingPayload,
    DependencyScanPayload,
    SecretScanPayload,
    RbacAuditPayload,
    SecurityReportPayload,
)
from app.services.security import SecurityGenerationService


def _make_payload(
    project_id=None,
    workflow_id=None,
    backend_generation_id=None,
    frontend_generation_id=None,
    design_id=None,
    report_id=None,
    threat_models=None,
    security_findings=None,
    dependency_scans=None,
    secret_scans=None,
    rbac_audits=None,
    security_reports=None,
) -> SecurityGenerationPayload:
    return SecurityGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        backend_generation_id=backend_generation_id or uuid.uuid4(),
        frontend_generation_id=frontend_generation_id or uuid.uuid4(),
        design_id=design_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        notes="Test Security assessment",
        threat_models=threat_models or [
            ThreatModelPayload(
                threat_source="External Attacker",
                vulnerability="SQL Injection in login",
                impact="Database compromise",
                risk_level="HIGH",
                mitigation="Use ORM",
            )
        ],
        security_findings=security_findings or [
            SecurityFindingPayload(
                title="Hardcoded API Key",
                description="Plaintext key detected in code",
                severity="HIGH",
                remediation="Use env variables",
                finding_type="Secret Exposure",
                metadata_json={"file": "config.py"},
            )
        ],
        dependency_scans=dependency_scans or [
            DependencyScanPayload(
                package_name="fastapi",
                installed_version="0.109.0",
                latest_version="0.111.0",
                vulnerabilities_json={"cves": []},
                status="PASSED",
            )
        ],
        secret_scans=secret_scans or [
            SecretScanPayload(
                file_path="config.py",
                secret_type="API Key",
                line_number=22,
                status="WARNING",
            )
        ],
        rbac_audits=rbac_audits or [
            RbacAuditPayload(
                role_name="User",
                permissions_json={"can_read": True},
                audit_result="Pass",
                status="PASSED",
            )
        ],
        security_reports=security_reports or [
            SecurityReportPayload(
                report_name="Audit Report",
                overall_risk_score=90.0,
                recommendations_json={"rec": []},
                summary="Clean",
            )
        ],
    )


def _make_svc(db: AsyncSession) -> SecurityGenerationService:
    return SecurityGenerationService(
        generation_repo=SecurityGenerationRepository(db),
        threat_model_repo=ThreatModelRepository(db),
        finding_repo=SecurityFindingRepository(db),
        dependency_repo=DependencyScanRepository(db),
        secret_repo=SecretScanRepository(db),
        rbac_repo=RbacAuditRepository(db),
        report_repo=SecurityReportRepository(db),
        db=db,
    )


# ── 1. TestSecurityGenerationCreation ─────────────────────────────────────────

class TestSecurityGenerationCreation:

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

        tms = await svc.list_threat_models(gen.generation_id)
        findings = await svc.list_security_findings(gen.generation_id)
        deps = await svc.list_dependency_scans(gen.generation_id)
        secrets = await svc.list_secret_scans(gen.generation_id)
        rbacs = await svc.list_rbac_audits(gen.generation_id)
        reps = await svc.list_security_reports(gen.generation_id)

        assert len(tms) == 1
        assert len(findings) == 1
        assert len(deps) == 1
        assert len(secrets) == 1
        assert len(rbacs) == 1
        assert len(reps) == 1

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
        with patch("app.services.security._kafka_available", True), \
             patch("app.services.security.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "security.generation.events"
        assert event["event_type"] == "security.generation.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_requested_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.security._kafka_available", True), \
             patch("app.services.security.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "security.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.security._kafka_available", True), \
             patch("app.services.security.KafkaEventPublisher", return_value=mock_pub):
            svc = _make_svc(db_session)
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="Recheck settings",
            )

        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "security.generation.requested"


# ── 3. TestAPIEndpoints ───────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/security/generate",
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
            f"/api/v1/security/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_get_threat_model_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/security/threat-models/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ── 4. TestSecurityAgentTools ─────────────────────────────────────────────────

class TestSecurityAgentTools:

    def test_threat_model_tool_produces_data(self):
        from agent import threat_model_tool
        result = threat_model_tool("Attacker", "XSS", "Data Leak", "HIGH", "Escape HTML")
        assert result["threat_source"] == "Attacker"
        assert result["vulnerability"] == "XSS"
        assert result["impact"] == "Data Leak"
        assert result["risk_level"] == "HIGH"
        assert result["mitigation"] == "Escape HTML"

    def test_dependency_scan_tool_produces_data(self):
        from agent import dependency_scan_tool
        result = dependency_scan_tool("fastapi", "0.109.0", "0.111.0", {"cves": []}, "PASSED")
        assert result["package_name"] == "fastapi"
        assert result["installed_version"] == "0.109.0"
        assert result["status"] == "PASSED"

    def test_secret_scan_tool_produces_data(self):
        from agent import secret_scan_tool
        result = secret_scan_tool("config.py", "API Key", 22, "WARNING")
        assert result["file_path"] == "config.py"
        assert result["secret_type"] == "API Key"
        assert result["line_number"] == 22
        assert result["status"] == "WARNING"

    def test_rbac_audit_tool_produces_data(self):
        from agent import rbac_audit_tool
        result = rbac_audit_tool("User", {"can_read": True}, "Pass", "PASSED")
        assert result["role_name"] == "User"
        assert result["permissions_json"] == {"can_read": True}
        assert result["audit_result"] == "Pass"

    def test_risk_scoring_tool_produces_data(self):
        from agent import risk_scoring_tool
        result = risk_scoring_tool(2, 2)
        assert result == 70.0  # 100 - 10 - 20

    def test_security_report_tool_produces_data(self):
        from agent import security_report_tool
        result = security_report_tool("Audit", 90.0, {"rec": []}, "Pass")
        assert result["report_name"] == "Audit"
        assert result["overall_risk_score"] == 90.0


# ── 5. TestSecurityAgentExecute ───────────────────────────────────────────────

class TestSecurityAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import SecurityAgent
        agent = SecurityAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "threat_models" in result
        assert "security_findings" in result
        assert "dependency_scans" in result
        assert "secret_scans" in result
        assert "rbac_audits" in result
        assert "security_reports" in result
        assert len(result["threat_models"]) == 2
        assert len(result["security_findings"]) == 2
        assert len(result["dependency_scans"]) == 2
        assert len(result["secret_scans"]) == 2
        assert len(result["rbac_audits"]) == 2
        assert len(result["security_reports"]) == 1


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

    def test_on_security_generation_completed_resumes_workflow(self):
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

        result = mgr.on_security_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"threat_count": 2, "finding_count": 2},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

        # Verify security.review.requested event was published
        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "security.review.requested" in published_topics

    def test_on_security_generation_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_security_generation_failed(
            workflow_id=wf_id,
            error="Vulnerability scan timed out",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
