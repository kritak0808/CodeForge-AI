"""
CodeForge AI Agent Worker Pool – Entry Point (Milestone 7 updated)

Listens to Kafka topics and dispatches tasks to the appropriate agent:
  - architect.requested  → ArchitectAgent
  - database.design.requested → DatabaseAgent

Both agents are auto-registered in the shared AgentRegistry on import.
"""
import json
import logging
import os
import sys
import time
import uuid
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-workers")

# ── Resolve agent-orchestrator path for KafkaEventPublisher ───────────────
orchestrator_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "agent-orchestrator")
)
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

# ── Resolve API app path for DatabaseDesignService ───────────────────────
api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if api_path not in sys.path:
    sys.path.insert(0, api_path)

from agent import agent_registry, DatabaseAgent, BackendAgent, FrontendAgent, QAAgent, SecurityAgent, DevOpsAgent, CostOptimizationAgent, ObservabilityAgent, AutonomousControllerAgent  # noqa: E402

from app.database import AsyncSessionLocal
import asyncio

def _get_or_create_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


# ── Database imports
from app.schemas.database import DatabaseDesignPayload
from app.services.database import DatabaseDesignService
from app.repositories.database import (
    DatabaseDesignRepository,
    DatabaseEntityRepository,
    DatabaseRelationshipRepository,
    DatabaseIndexRepository,
    MigrationPlanRepository,
    QueryOptimizationRepository,
)

# ── Backend imports
from app.schemas.backend import BackendGenerationPayload
from app.services.backend import BackendGenerationService
from app.repositories.backend import (
    BackendGenerationRepository,
    ApiEndpointRepository,
    ServiceDefinitionRepository,
    RepositoryDefinitionRepository,
    BusinessRuleRepository,
    ApiTestReportRepository,
)

# ── Frontend imports
from app.schemas.frontend import FrontendGenerationPayload
from app.services.frontend import FrontendGenerationService
from app.repositories.frontend import (
    FrontendGenerationRepository,
    FrontendPageRepository,
    FrontendComponentRepository,
    FrontendFormRepository,
    FrontendHookRepository,
    FrontendTestReportRepository,
    UiDesignArtifactRepository,
)

# ── QA imports
from app.schemas.qa import QaGenerationPayload
from app.services.qa import QaGenerationService
from app.repositories.qa import (
    QaGenerationRepository,
    QaTestSuiteRepository,
    QaTestCaseRepository,
    QaTestRunRepository,
    QaBugReportRepository,
    QaCoverageReportRepository,
    QaQualityMetricsRepository,
)

# ── Security imports
from app.schemas.security import SecurityGenerationPayload
from app.services.security import SecurityGenerationService
from app.repositories.security import (
    SecurityGenerationRepository,
    ThreatModelRepository,
    SecurityFindingRepository,
    DependencyScanRepository,
    SecretScanRepository,
    RbacAuditRepository,
    SecurityReportRepository,
)

# ── DevOps imports
from app.schemas.devops import DevOpsGenerationPayload
from app.services.devops import DevOpsGenerationService
from app.repositories.devops import (
    DevopsGenerationRepository,
    DockerArtifactRepository,
    KubernetesArtifactRepository,
    HelmArtifactRepository,
    TerraformArtifactRepository,
    CicdPipelineRepository,
    DeploymentTemplateRepository,
)

from app.schemas.cost import CostGenerationPayload, CostReportPayload, ResourceUsageMetricPayload, OptimizationRecommendationPayload, SavingsEstimatePayload, CostAlertPayload
from app.schemas.observability import ObservabilityGenerationPayload, AgentMetricPayload, WorkflowMetricPayload, ApiMetricPayload, SystemMetricPayload, ErrorEventPayload, AlertRulePayload, AlertEventPayload
from app.services.cost import CostOptimizationService
from app.repositories.cost import (
    CostGenerationRepository,
    CostReportRepository,
    ResourceUsageMetricRepository,
    OptimizationRecommendationRepository,
    SavingsEstimateRepository,
    BudgetPolicyRepository,
    CostAlertRepository,
)
from app.services.observability import ObservabilityService
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

# ── Kafka publisher (best-effort – workers run even without Kafka) ─────────
try:
    from event_publisher import KafkaEventPublisher
    event_pub = KafkaEventPublisher()
    KAFKA_AVAILABLE = True
    logger.info("Kafka publisher initialised.")
except Exception as exc:
    event_pub = None
    KAFKA_AVAILABLE = False
    logger.warning(f"Kafka publisher unavailable (running in stub mode): {exc}")


# ────────────────────────────────────────────────────────────────────────────
# Kafka topic handlers
# ────────────────────────────────────────────────────────────────────────────

def _publish(topic: str, payload: dict) -> None:
    if KAFKA_AVAILABLE and event_pub:
        try:
            event_pub.publish(topic, payload)
        except Exception as exc:
            logger.warning(f"Kafka publish failed [{topic}]: {exc}")
    else:
        logger.debug(f"[Stub] Would publish to '{topic}': {payload}")


def handle_database_design_requested(message: dict) -> None:
    """
    Consumes a 'database.design.requested' Kafka message, runs the
    DatabaseAgent pipeline, and publishes the completion event.
    """
    workflow_id: Optional[str] = message.get("workflow_id")
    project_id: Optional[str] = message.get("project_id")
    report_id: Optional[str] = message.get("report_id")

    logger.info(
        f"[Worker] Received database.design.requested: "
        f"workflow_id={workflow_id} project_id={project_id}"
    )

    agent: DatabaseAgent = agent_registry.get_agent("DatabaseAgent")
    if not agent:
        logger.error("[Worker] DatabaseAgent not found in registry!")
        _publish(
            "database.design.events",
            {
                "event_type": "database.design.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": "DatabaseAgent not registered",
            },
        )
        return

    try:
        # Run the full agent pipeline
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "report_id": report_id,
            "entities": message.get("entities", []),
            "relationships": message.get("relationships", []),
            "query_patterns": message.get("query_patterns", ["standard lookup", "json metadata"]),
        })

        db_payload = DatabaseDesignPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            report_id=uuid.UUID(report_id) if report_id else None,
            sql_schema=result.get("sql_schema"),
            er_diagram_text=result.get("er_diagram_text"),
            er_diagram_mermaid=result.get("er_diagram_mermaid"),
            notes=result.get("notes"),
            entities=result.get("entities", []),
            relationships=result.get("relationships", []),
            indexes=result.get("indexes", []),
            migration=result.get("migration"),
            optimizations=result.get("optimizations", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = DatabaseDesignService(
                    design_repo=DatabaseDesignRepository(session),
                    entity_repo=DatabaseEntityRepository(session),
                    relationship_repo=DatabaseRelationshipRepository(session),
                    index_repo=DatabaseIndexRepository(session),
                    migration_repo=MigrationPlanRepository(session),
                    optimization_repo=QueryOptimizationRepository(session),
                    db=session,
                )
                return await svc.create_design_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        design = loop.run_until_complete(persist())
        design_id_str = str(design.design_id)

        logger.info(
            f"[Worker] DatabaseAgent pipeline complete and persisted: design_id={design_id_str}"
        )

        _publish(
            "database.design.events",
            {
                "event_type": "database.design.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "design_id": design_id_str,
                "report_id": report_id,
                "result_summary": {
                    "entity_count": len(result.get("entities", [])),
                    "relationship_count": len(result.get("relationships", [])),
                    "index_count": len(result.get("indexes", [])),
                    "optimization_count": len(result.get("optimizations", [])),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] DatabaseAgent pipeline failed: {exc}")
        _publish(
            "database.design.events",
            {
                "event_type": "database.design.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": str(exc),
            },
        )


def handle_backend_generation_requested(message: dict) -> None:
    """
    Consumes a 'backend.generation.requested' Kafka message, runs the
    BackendAgent pipeline, and publishes the completion event.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")
    design_id = message.get("design_id")
    report_id = message.get("report_id")

    logger.info(
        f"[Worker] Received backend.generation.requested: "
        f"workflow_id={workflow_id} generation_id={generation_id}"
    )

    agent: BackendAgent = agent_registry.get_agent("BackendAgent")
    if not agent:
        logger.error("[Worker] BackendAgent not found in registry!")
        _publish(
            "backend.generation.events",
            {
                "event_type": "backend.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": "BackendAgent not registered",
            },
        )
        return

    try:
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "design_id": design_id,
            "report_id": report_id,
            "entities": message.get("entities", []),
            "framework": message.get("framework", "FastAPI"),
            "language": message.get("language", "Python"),
        })

        db_payload = BackendGenerationPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            design_id=uuid.UUID(design_id) if design_id else None,
            report_id=uuid.UUID(report_id) if report_id else None,
            framework=result.get("framework", "FastAPI"),
            language=result.get("language", "Python"),
            openapi_spec=result.get("openapi_spec"),
            notes=result.get("notes"),
            endpoints=result.get("endpoints", []),
            services=result.get("services", []),
            repositories=result.get("repositories", []),
            business_rules=result.get("business_rules", []),
            test_reports=result.get("test_reports", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = BackendGenerationService(
                    generation_repo=BackendGenerationRepository(session),
                    endpoint_repo=ApiEndpointRepository(session),
                    service_repo=ServiceDefinitionRepository(session),
                    repository_repo=RepositoryDefinitionRepository(session),
                    rule_repo=BusinessRuleRepository(session),
                    test_repo=ApiTestReportRepository(session),
                    db=session,
                )
                return await svc.create_generation_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist())
        gen_id_str = str(gen.generation_id)

        logger.info(
            f"[Worker] BackendAgent pipeline complete and persisted: generation_id={gen_id_str}"
        )

        _publish(
            "backend.generation.events",
            {
                "event_type": "backend.generation.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": gen_id_str,
                "result_summary": {
                    "endpoint_count": len(result.get("endpoints", [])),
                    "service_count": len(result.get("services", [])),
                    "repository_count": len(result.get("repositories", [])),
                    "test_count": len(result.get("test_reports", [])),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] BackendAgent pipeline failed: {exc}")
        _publish(
            "backend.generation.events",
            {
                "event_type": "backend.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": str(exc),
            },
        )

def handle_frontend_generation_requested(message: dict) -> None:
    """
    Consumes a 'frontend.generation.requested' Kafka message, runs the
    FrontendAgent pipeline, and publishes the completion event.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")
    backend_generation_id = message.get("backend_generation_id")
    design_id = message.get("design_id")
    report_id = message.get("report_id")

    logger.info(
        f"[Worker] Received frontend.generation.requested: "
        f"workflow_id={workflow_id} generation_id={generation_id}"
    )

    agent: FrontendAgent = agent_registry.get_agent("FrontendAgent")
    if not agent:
        logger.error("[Worker] FrontendAgent not found in registry!")
        _publish(
            "frontend.generation.events",
            {
                "event_type": "frontend.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": "FrontendAgent not registered",
            },
        )
        return

    try:
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "backend_generation_id": backend_generation_id,
            "design_id": design_id,
            "report_id": report_id,
            "framework": message.get("framework", "Next.js 15"),
            "language": message.get("language", "TypeScript"),
        })

        db_payload = FrontendGenerationPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            backend_generation_id=uuid.UUID(backend_generation_id) if backend_generation_id else None,
            design_id=uuid.UUID(design_id) if design_id else None,
            report_id=uuid.UUID(report_id) if report_id else None,
            framework=result.get("framework", "Next.js 15"),
            language=result.get("language", "TypeScript"),
            notes=result.get("notes"),
            pages=result.get("pages", []),
            components=result.get("components", []),
            forms=result.get("forms", []),
            hooks=result.get("hooks", []),
            test_reports=result.get("test_reports", []),
            ui_design_artifacts=result.get("ui_design_artifacts", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = FrontendGenerationService(
                    generation_repo=FrontendGenerationRepository(session),
                    page_repo=FrontendPageRepository(session),
                    component_repo=FrontendComponentRepository(session),
                    form_repo=FrontendFormRepository(session),
                    hook_repo=FrontendHookRepository(session),
                    test_repo=FrontendTestReportRepository(session),
                    ui_design_artifact_repo=UiDesignArtifactRepository(session),
                    db=session,
                )
                return await svc.create_generation_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist())
        gen_id_str = str(gen.generation_id)

        logger.info(
            f"[Worker] FrontendAgent pipeline complete and persisted: generation_id={gen_id_str}"
        )

        _publish(
            "frontend.generation.events",
            {
                "event_type": "frontend.generation.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": gen_id_str,
                "result_summary": {
                    "page_count": len(result.get("pages", [])),
                    "component_count": len(result.get("components", [])),
                    "form_count": len(result.get("forms", [])),
                    "hook_count": len(result.get("hooks", [])),
                    "test_count": len(result.get("test_reports", [])),
                    "ui_artifact_count": len(result.get("ui_design_artifacts", [])),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] FrontendAgent pipeline failed: {exc}")
        _publish(
            "frontend.generation.events",
            {
                "event_type": "frontend.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": str(exc),
            },
        )


def handle_qa_generation_requested(message: dict) -> None:
    """
    Consumes a 'qa.generation.requested' Kafka message, runs the
    QAAgent pipeline, and publishes the completion event.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")
    backend_generation_id = message.get("backend_generation_id")
    frontend_generation_id = message.get("frontend_generation_id")
    design_id = message.get("design_id")
    report_id = message.get("report_id")

    logger.info(
        f"[Worker] Received qa.generation.requested: "
        f"workflow_id={workflow_id} generation_id={generation_id}"
    )

    agent: QAAgent = agent_registry.get_agent("QAAgent")
    if not agent:
        logger.error("[Worker] QAAgent not found in registry!")
        _publish(
            "qa.generation.events",
            {
                "event_type": "qa.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": "QAAgent not registered",
            },
        )
        return

    try:
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "backend_generation_id": backend_generation_id,
            "frontend_generation_id": frontend_generation_id,
            "design_id": design_id,
            "report_id": report_id,
            "qa_force_fail": message.get("qa_force_fail", False),
        })

        db_payload = QaGenerationPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            backend_generation_id=uuid.UUID(backend_generation_id) if backend_generation_id else None,
            frontend_generation_id=uuid.UUID(frontend_generation_id) if frontend_generation_id else None,
            design_id=uuid.UUID(design_id) if design_id else None,
            report_id=uuid.UUID(report_id) if report_id else None,
            notes=result.get("notes"),
            test_suites=result.get("test_suites", []),
            test_cases=result.get("test_cases", []),
            test_runs=result.get("test_runs", []),
            bug_reports=result.get("bug_reports", []),
            coverage_reports=result.get("coverage_reports", []),
            quality_metrics=result.get("quality_metrics", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = QaGenerationService(
                    generation_repo=QaGenerationRepository(session),
                    suite_repo=QaTestSuiteRepository(session),
                    case_repo=QaTestCaseRepository(session),
                    run_repo=QaTestRunRepository(session),
                    bug_repo=QaBugReportRepository(session),
                    coverage_repo=QaCoverageReportRepository(session),
                    metrics_repo=QaQualityMetricsRepository(session),
                    db=session,
                )
                return await svc.create_generation_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist())
        gen_id_str = str(gen.generation_id)

        logger.info(
            f"[Worker] QAAgent pipeline complete and persisted: generation_id={gen_id_str}"
        )

        _publish(
            "qa.generation.events",
            {
                "event_type": "qa.generation.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": gen_id_str,
                "result_summary": {
                    "suite_count": len(result.get("test_suites", [])),
                    "case_count": len(result.get("test_cases", [])),
                    "run_count": len(result.get("test_runs", [])),
                    "bug_count": len(result.get("bug_reports", [])),
                    "coverage_count": len(result.get("coverage_reports", [])),
                    "metrics_count": len(result.get("quality_metrics", [])),
                },
                "errors": [bug["description"] for bug in result.get("bug_reports", []) if bug.get("severity") in ("CRITICAL", "HIGH")],
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] QAAgent pipeline failed: {exc}")
        _publish(
            "qa.generation.events",
            {
                "event_type": "qa.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": str(exc),
            },
        )


def handle_security_generation_requested(message: dict) -> None:
    """
    Consumes a 'security.generation.requested' Kafka message, runs the
    SecurityAgent pipeline, and publishes the completion event.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")
    backend_generation_id = message.get("backend_generation_id")
    frontend_generation_id = message.get("frontend_generation_id")
    design_id = message.get("design_id")
    report_id = message.get("report_id")

    logger.info(
        f"[Worker] Received security.generation.requested: "
        f"workflow_id={workflow_id} generation_id={generation_id}"
    )

    agent: SecurityAgent = agent_registry.get_agent("SecurityAgent")
    if not agent:
        logger.error("[Worker] SecurityAgent not found in registry!")
        _publish(
            "security.generation.events",
            {
                "event_type": "security.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": "SecurityAgent not registered",
            },
        )
        return

    try:
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "backend_generation_id": backend_generation_id,
            "frontend_generation_id": frontend_generation_id,
            "design_id": design_id,
            "report_id": report_id,
        })

        db_payload = SecurityGenerationPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            backend_generation_id=uuid.UUID(backend_generation_id) if backend_generation_id else None,
            frontend_generation_id=uuid.UUID(frontend_generation_id) if frontend_generation_id else None,
            design_id=uuid.UUID(design_id) if design_id else None,
            report_id=uuid.UUID(report_id) if report_id else None,
            notes=result.get("notes"),
            threat_models=result.get("threat_models", []),
            security_findings=result.get("security_findings", []),
            dependency_scans=result.get("dependency_scans", []),
            secret_scans=result.get("secret_scans", []),
            rbac_audits=result.get("rbac_audits", []),
            security_reports=result.get("security_reports", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = SecurityGenerationService(
                    generation_repo=SecurityGenerationRepository(session),
                    threat_model_repo=ThreatModelRepository(session),
                    finding_repo=SecurityFindingRepository(session),
                    dependency_repo=DependencyScanRepository(session),
                    secret_repo=SecretScanRepository(session),
                    rbac_repo=RbacAuditRepository(session),
                    report_repo=SecurityReportRepository(session),
                    db=session,
                )
                return await svc.create_generation_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist())
        gen_id_str = str(gen.generation_id)

        logger.info(
            f"[Worker] SecurityAgent pipeline complete and persisted: generation_id={gen_id_str}"
        )

        _publish(
            "security.generation.events",
            {
                "event_type": "security.generation.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": gen_id_str,
                "result_summary": {
                    "threat_count": len(result.get("threat_models", [])),
                    "finding_count": len(result.get("security_findings", [])),
                    "dependency_count": len(result.get("dependency_scans", [])),
                    "secret_count": len(result.get("secret_scans", [])),
                    "rbac_count": len(result.get("rbac_audits", [])),
                    "report_count": len(result.get("security_reports", [])),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] SecurityAgent pipeline failed: {exc}")
        _publish(
            "security.generation.events",
            {
                "event_type": "security.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": str(exc),
            },
        )


def handle_devops_generation_requested(message: dict) -> None:
    """
    Consumes a 'devops.generation.requested' Kafka message, runs the
    DevOpsAgent pipeline, and publishes the completion event.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")
    backend_generation_id = message.get("backend_generation_id")
    frontend_generation_id = message.get("frontend_generation_id")
    design_id = message.get("design_id")
    report_id = message.get("report_id")

    logger.info(
        f"[Worker] Received devops.generation.requested: "
        f"workflow_id={workflow_id} generation_id={generation_id}"
    )

    agent: DevOpsAgent = agent_registry.get_agent("DevOpsAgent")
    if not agent:
        logger.error("[Worker] DevOpsAgent not found in registry!")
        _publish(
            "devops.generation.events",
            {
                "event_type": "devops.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": "DevOpsAgent not registered",
            },
        )
        return

    try:
        result = agent.execute({
            "workflow_id": workflow_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "backend_generation_id": backend_generation_id,
            "frontend_generation_id": frontend_generation_id,
            "design_id": design_id,
            "report_id": report_id,
        })

        db_payload = DevOpsGenerationPayload(
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            project_id=uuid.UUID(project_id),
            backend_generation_id=uuid.UUID(backend_generation_id) if backend_generation_id else None,
            frontend_generation_id=uuid.UUID(frontend_generation_id) if frontend_generation_id else None,
            design_id=uuid.UUID(design_id) if design_id else None,
            report_id=uuid.UUID(report_id) if report_id else None,
            notes=result.get("notes"),
            docker_artifacts=result.get("docker_artifacts", []),
            kubernetes_artifacts=result.get("kubernetes_artifacts", []),
            helm_artifacts=result.get("helm_artifacts", []),
            terraform_artifacts=result.get("terraform_artifacts", []),
            cicd_pipelines=result.get("cicd_pipelines", []),
            deployment_templates=result.get("deployment_templates", []),
        )

        async def persist():
            async with AsyncSessionLocal() as session:
                svc = DevOpsGenerationService(
                    generation_repo=DevopsGenerationRepository(session),
                    docker_repo=DockerArtifactRepository(session),
                    kubernetes_repo=KubernetesArtifactRepository(session),
                    helm_repo=HelmArtifactRepository(session),
                    terraform_repo=TerraformArtifactRepository(session),
                    pipeline_repo=CicdPipelineRepository(session),
                    template_repo=DeploymentTemplateRepository(session),
                    db=session,
                )
                return await svc.create_generation_from_payload(db_payload)

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist())
        gen_id_str = str(gen.generation_id)

        logger.info(
            f"[Worker] DevOpsAgent pipeline complete and persisted: generation_id={gen_id_str}"
        )

        _publish(
            "devops.generation.events",
            {
                "event_type": "devops.generation.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": gen_id_str,
                "result_summary": {
                    "docker_count": len(result.get("docker_artifacts", [])),
                    "kubernetes_count": len(result.get("kubernetes_artifacts", [])),
                    "helm_count": len(result.get("helm_artifacts", [])),
                    "terraform_count": len(result.get("terraform_artifacts", [])),
                    "pipeline_count": len(result.get("cicd_pipelines", [])),
                    "template_count": len(result.get("deployment_templates", [])),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] DevOpsAgent pipeline failed: {exc}")
        _publish(
            "devops.generation.events",
            {
                "event_type": "devops.generation.failed",
                "workflow_id": workflow_id,
                "generation_id": generation_id,
                "error": str(exc),
            },
        )
def handle_agent_review_requested(message: dict) -> None:
    review_id = message.get("review_id")
    session_id = message.get("session_id")
    reviewer_agent = message.get("reviewer_agent")
    logger.info(f"[Worker] Consuming agent.review.requested for review_id={review_id}")
    
    _publish(
        "agent.review.completed",
        {
            "event_type": "agent.review.completed",
            "review_id": review_id,
            "session_id": session_id,
            "reviewer_agent": reviewer_agent,
            "status": "APPROVED",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

def handle_agent_vote_started(message: dict) -> None:
    session_id = message.get("session_id")
    topic = message.get("topic")
    voters = message.get("voters", [])
    logger.info(f"[Worker] Consuming agent.vote.started for topic={topic}")
    
    for voter in voters:
        _publish(
            "agent.vote.completed",
            {
                "event_type": "agent.vote.completed",
                "session_id": session_id,
                "topic": topic,
                "voter_agent": voter,
                "decision": "YES",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

def handle_agent_conflict_created(message: dict) -> None:
    conflict_id = message.get("conflict_id")
    session_id = message.get("session_id")
    title = message.get("title")
    logger.info(f"[Worker] Consuming agent.conflict.created for conflict_id={conflict_id}")
    
    _publish(
        "agent.conflict.resolved",
        {
            "event_type": "agent.conflict.resolved",
            "conflict_id": conflict_id,
            "session_id": session_id,
            "resolved_by": "LeadAgent",
            "strategy": "Arbitration",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


def handle_agent_task(message: dict) -> None:
    """
    Generic task handler for the agent.tasks topic.
    Routes tasks to the correct agent based on the 'agent_id' field.
    """
    agent_id = message.get("agent_id", "ResearchAgent")
    task_description = message.get("task_description", "")
    context = message.get("context", {})

    agent = agent_registry.get_agent(agent_id)
    if not agent:
        logger.warning(f"[Worker] Agent '{agent_id}' not found in registry. Skipping task.")
        return

    logger.info(f"[Worker] Dispatching task to agent '{agent_id}'")
    result = agent.execute_task(task_description, context)
    logger.info(f"[Worker] Agent '{agent_id}' completed task: status={result.get('status')}")


def handle_cost_started(message: dict) -> None:
    """
    Consumes a 'cost.started' Kafka message, runs the CostOptimizationAgent pipeline,
    persists the results using CostOptimizationService, and publishes completed/failed events.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    generation_id = message.get("generation_id")

    logger.info(
        f"[Worker] Received cost.started: workflow_id={workflow_id} project_id={project_id}"
    )

    agent = agent_registry.get_agent("CostOptimizationAgent")
    if not agent:
        logger.error("[Worker] CostOptimizationAgent not found in registry!")
        _publish(
            "cost.generation.events",
            {
                "event_type": "cost.analysis.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": "CostOptimizationAgent not registered",
            },
        )
        return

    import asyncio
    import uuid

    budget_limit = 500.0
    alert_threshold = 0.8
    try:
        async def fetch_policy():
            async with AsyncSessionLocal() as session:
                repo = BudgetPolicyRepository(session)
                return await repo.get_by_project(uuid.UUID(project_id))
        
        loop = _get_or_create_event_loop()
        policy = loop.run_until_complete(fetch_policy())
        if policy:
            budget_limit = policy.monthly_budget
            alert_threshold = policy.alert_threshold
    except Exception as exc:
        logger.warning(f"[Worker] Budget policy not loaded: {exc}. Falling back to default: budget={budget_limit}, threshold={alert_threshold}.")

    try:
        payload = {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "budget_limit": budget_limit,
            "alert_threshold": alert_threshold,
        }
        res = agent.execute(payload)

        db_payload = CostGenerationPayload(
            project_id=uuid.UUID(project_id),
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            total_cost=res["total_cost"],
            estimated_monthly_cost=res["estimated_monthly_cost"],
            currency=res["currency"],
            cost_reports=[CostReportPayload(**x) for x in res["cost_reports"]],
            resource_usage_metrics=[ResourceUsageMetricPayload(**x) for x in res["resource_usage_metrics"]],
            optimization_recommendations=[OptimizationRecommendationPayload(**x) for x in res["optimization_recommendations"]],
            savings_estimates=[SavingsEstimatePayload(**x) for x in res["savings_estimates"]],
            cost_alerts=[CostAlertPayload(**x) for x in res["cost_alerts"]],
        )

        async def persist_cost():
            async with AsyncSessionLocal() as session:
                svc = CostOptimizationService(
                    generation_repo=CostGenerationRepository(session),
                    report_repo=CostReportRepository(session),
                    metric_repo=ResourceUsageMetricRepository(session),
                    recommendation_repo=OptimizationRecommendationRepository(session),
                    savings_repo=SavingsEstimateRepository(session),
                    policy_repo=BudgetPolicyRepository(session),
                    alert_repo=CostAlertRepository(session),
                    db=session,
                )
                gen = await svc.create_generation_from_payload(db_payload)
                gen._event_pub = svc._event_pub
                return gen

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist_cost())

        logger.info(
            f"[Worker] CostOptimizationAgent pipeline complete and persisted. "
            f"generation_id={gen.generation_id}"
        )

        _publish(
            "cost.generation.events",
            {
                "event_type": "cost.analysis.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": str(gen.generation_id),
                "result_summary": {
                    "total_cost": res["total_cost"],
                    "estimated_monthly_cost": res["estimated_monthly_cost"],
                    "recommendation_count": len(res["optimization_recommendations"]),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] CostOptimizationAgent pipeline failed: {exc}")
        _publish(
            "cost.generation.events",
            {
                "event_type": "cost.analysis.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": str(exc),
            },
        )


def handle_observability_started(message: dict) -> None:
    """
    Consumes a 'observability.started' Kafka message, runs the ObservabilityAgent pipeline,
    persists the results using ObservabilityService, and publishes completed/failed events.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")

    logger.info(
        f"[Worker] Received observability.started: workflow_id={workflow_id} project_id={project_id}"
    )

    from agent import _observability_agent_instance
    agent = _observability_agent_instance

    import asyncio
    import uuid

    try:
        payload = {
            "workflow_id": workflow_id,
            "project_id": project_id,
        }
        res = agent.execute(payload)

        db_payload = ObservabilityGenerationPayload(
            project_id=uuid.UUID(project_id),
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            notes=res["notes"],
            agent_metrics=[AgentMetricPayload(**x) for x in res["agent_metrics"]],
            workflow_metrics=[WorkflowMetricPayload(**x) for x in res["workflow_metrics"]],
            api_metrics=[ApiMetricPayload(**x) for x in res["api_metrics"]],
            system_metrics=[SystemMetricPayload(**x) for x in res["system_metrics"]],
            error_events=[ErrorEventPayload(**x) for x in res["error_events"]],
            alert_rules=[AlertRulePayload(**x) for x in res["alert_rules"]],
            alert_events=[AlertEventPayload(**x) for x in res["alert_events"]],
        )

        async def persist_obs():
            async with AsyncSessionLocal() as session:
                svc = ObservabilityService(
                    generation_repo=ObservabilityGenerationRepository(session),
                    agent_metric_repo=AgentMetricRepository(session),
                    workflow_metric_repo=WorkflowMetricRepository(session),
                    api_metric_repo=ApiMetricRepository(session),
                    system_metric_repo=SystemMetricRepository(session),
                    error_event_repo=ErrorEventRepository(session),
                    alert_rule_repo=AlertRuleRepository(session),
                    alert_event_repo=AlertEventRepository(session),
                    db=session,
                )
                gen = await svc.create_generation_from_payload(db_payload)
                gen._event_pub = svc._event_pub
                return gen

        loop = _get_or_create_event_loop()
        gen = loop.run_until_complete(persist_obs())

        logger.info(
            f"[Worker] ObservabilityAgent pipeline complete and persisted. "
            f"generation_id={gen.generation_id}"
        )

        _publish(
            "observability.generation.events",
            {
                "event_type": "observability.completed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "generation_id": str(gen.generation_id),
                "result_summary": {
                    "agent_count": len(res["agent_metrics"]),
                    "alert_count": len(res["alert_events"]),
                },
            },
        )

    except Exception as exc:
        logger.exception(f"[Worker] ObservabilityAgent pipeline failed: {exc}")
        _publish(
            "observability.generation.events",
            {
                "event_type": "observability.generation.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": str(exc),
            },
        )


# ────────────────────────────────────────────────────────────────────────────
# Simulated Kafka consumer loop
# ────────────────────────────────────────────────────────────────────────────

def handle_controller_started(message: dict) -> None:
    """
    Consumes a 'controller.started' Kafka message, runs the AutonomousControllerAgent pipeline,
    persists the results using AutonomousControllerService, and publishes decisions, retry,
    rollback, completed, or failed events.
    """
    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")

    logger.info(
        f"[Worker] Received controller.started: workflow_id={workflow_id} project_id={project_id}"
    )

    agent = agent_registry.get_agent("AutonomousControllerAgent")
    if not agent:
        logger.error("[Worker] AutonomousControllerAgent not found in registry!")
        _publish(
            "controller.failed",
            {
                "event_type": "controller.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": "AutonomousControllerAgent not registered",
            },
        )
        return

    import asyncio
    import uuid
    from datetime import datetime

    errors = message.get("errors", [])
    metrics = message.get("metrics", {})
    budget_limit = message.get("budget_limit", 1000.0)
    accumulated_cost = message.get("accumulated_cost", 0.0)
    retry_attempt = message.get("retry_attempt", 1)
    agent_heartbeats = message.get("agent_heartbeats", {"ResearchAgent": "OK", "DatabaseAgent": "OK"})

    try:
        payload = {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "current_step": message.get("current_step", "AUTONOMOUS_CONTROLLER"),
            "errors": errors,
            "metrics": metrics,
            "budget_limit": budget_limit,
            "accumulated_cost": accumulated_cost,
            "retry_attempt": retry_attempt,
            "agent_heartbeats": agent_heartbeats,
            "require_manual_approval": message.get("require_manual_approval", False),
        }
        res = agent.execute(payload)

        from app.schemas.controller import (
            AutonomousControllerPayload,
            WorkflowDecisionPayload,
            RetryHistoryPayload,
            FailureEventPayload,
            RollbackEventPayload,
            ExecutionPlanPayload,
            ControllerLogPayload,
        )

        decisions = []
        if "decision" in res:
            d = res["decision"]
            decisions.append(WorkflowDecisionPayload(
                step=res["current_step"],
                decision_type=d["decision_type"],
                reason=d["reason"],
                action_taken=d["action"]
            ))

        retries = []
        if res.get("retry_info"):
            r = res["retry_info"]
            retries.append(RetryHistoryPayload(
                step=r["step"],
                retry_attempt=r["retry_attempt"],
                max_retries=r["max_retries"],
                error_message=r["error_message"]
            ))

        failures = []
        if res.get("failure_analysis") and res["failure_analysis"].get("errors_detected"):
            f = res["failure_analysis"]
            for err in errors:
                failures.append(FailureEventPayload(
                    step=res["current_step"],
                    error_type="RUNTIME_ERROR",
                    error_message=str(err),
                    severity=f["severity"]
                ))

        rollbacks = []
        if res.get("rollback_info"):
            rb = res["rollback_info"]
            rollbacks.append(RollbackEventPayload(
                source_step=rb["source_step"],
                target_step=rb["target_step"],
                reason=rb["reason"],
                status=rb["status"]
            ))

        execution_plans = []
        if res.get("execution_plan"):
            p = res["execution_plan"]
            execution_plans.append(ExecutionPlanPayload(
                steps_json=p["steps"],
                current_step_index=p["current_step_index"],
                is_optimized=p["is_optimized"]
            ))

        status = "ACTIVE"
        dec_type = res["decision"]["decision_type"]
        if dec_type == "COMPLETE":
            status = "COMPLETED"
        elif dec_type == "FAIL":
            status = "FAILED"
        elif dec_type == "APPROVE":
            status = "PAUSED"
        elif dec_type == "RETRY":
            status = "ACTIVE"
        elif dec_type == "ROLLBACK":
            status = "ACTIVE"

        db_payload = AutonomousControllerPayload(
            project_id=uuid.UUID(project_id),
            workflow_id=uuid.UUID(workflow_id) if workflow_id else None,
            status=status,
            current_step=res["current_step"],
            budget_limit=budget_limit,
            decisions=decisions,
            retries=retries,
            failures=failures,
            rollbacks=rollbacks,
            execution_plans=execution_plans,
            logs=[ControllerLogPayload(level="INFO", message=res["decision"]["reason"])],
        )

        async def persist_controller():
            from app.services.controller import AutonomousControllerService
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
            async with AsyncSessionLocal() as session:
                svc = AutonomousControllerService(
                    controller_repo=AutonomousControllerRepository(session),
                    decision_repo=WorkflowDecisionRepository(session),
                    health_repo=AgentHealthRepository(session),
                    retry_repo=RetryHistoryRepository(session),
                    failure_repo=FailureEventRepository(session),
                    rollback_repo=RollbackEventRepository(session),
                    plan_repo=ExecutionPlanRepository(session),
                    log_repo=ControllerLogRepository(session),
                    db=session,
                )
                ctrl = await svc.create_controller_from_payload(db_payload)
                ctrl._event_pub = svc._event_pub
                return ctrl

        loop = _get_or_create_event_loop()
        ctrl = loop.run_until_complete(persist_controller())

        logger.info(
            f"[Worker] AutonomousControllerAgent pipeline complete and persisted. "
            f"controller_id={ctrl.controller_id}"
        )

        decision_type = res["decision"]["decision_type"]
        if decision_type == "RETRY":
            _publish("controller.retry", {
                "event_type": "controller.retry",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": workflow_id,
                "step": res["current_step"],
                "retry_attempt": retry_attempt,
            })
        elif decision_type == "ROLLBACK":
            _publish("controller.rollback", {
                "event_type": "controller.rollback",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": workflow_id,
                "source_step": res["current_step"],
                "target_step": res.get("rollback_info", {}).get("target_step", "RESEARCH"),
            })
        elif status == "COMPLETED" or decision_type == "ROUTE" or (res["decision"]["action"] == "PROCEED" and status == "ACTIVE"):
            _publish("controller.completed", {
                "event_type": "controller.completed",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": workflow_id,
                "project_id": project_id,
            })
        elif status == "FAILED" or decision_type == "FAIL":
            _publish("controller.failed", {
                "event_type": "controller.failed",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": res["decision"]["reason"],
            })

    except Exception as exc:
        logger.exception(f"[Worker] AutonomousControllerAgent pipeline failed: {exc}")
        _publish(
            "controller.failed",
            {
                "event_type": "controller.failed",
                "workflow_id": workflow_id,
                "project_id": project_id,
                "error": str(exc),
            },
        )


# Topic → handler mapping
TOPIC_HANDLERS = {
    "database.design.requested": handle_database_design_requested,
    "backend.generation.requested": handle_backend_generation_requested,
    "frontend.generation.requested": handle_frontend_generation_requested,
    "qa.generation.requested": handle_qa_generation_requested,
    "security.generation.requested": handle_security_generation_requested,
    "devops.generation.requested": handle_devops_generation_requested,
    "agent.review.requested": handle_agent_review_requested,
    "agent.vote.started": handle_agent_vote_started,
    "agent.conflict.created": handle_agent_conflict_created,
    "agent.tasks": handle_agent_task,
    "cost.started": handle_cost_started,
    "observability.started": handle_observability_started,
    "controller.started": handle_controller_started,
}


def _simulate_incoming_messages():
    """
    In production this function is replaced by a real Kafka consumer.
    Here we yield synthetic messages for local testing / smoke tests.
    """
    yield {
        "topic": "database.design.requested",
        "message": {
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "report_id": str(uuid.uuid4()),
            "entities": [
                {
                    "name": "Order",
                    "columns": [
                        {"name": "user_id", "type": "UUID", "nullable": False},
                        {"name": "total", "type": "NUMERIC(10,2)", "nullable": False},
                        {"name": "status", "type": "VARCHAR(50)", "nullable": False},
                    ],
                },
                {
                    "name": "OrderItem",
                    "columns": [
                        {"name": "order_id", "type": "UUID", "nullable": False},
                        {"name": "product_id", "type": "UUID", "nullable": False},
                        {"name": "quantity", "type": "INTEGER", "nullable": False},
                    ],
                },
            ],
            "relationships": [
                {"from": "OrderItem", "to": "Order", "cardinality": "1:N", "join_key": "order_id"},
            ],
        },
    }


def main():
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    logger.info("Starting CodeForge AI Agent Worker Pool…")
    logger.info(
        f"Registered agents: {agent_registry.list_registered_agents()}"
    )
    logger.info(
        f"Kafka available: {KAFKA_AVAILABLE} | "
        f"Subscribed topics: {list(TOPIC_HANDLERS.keys())}"
    )

    # Smoke test: run one simulated message then enter idle loop
    for envelope in _simulate_incoming_messages():
        topic = envelope["topic"]
        msg = envelope["message"]
        handler = TOPIC_HANDLERS.get(topic)
        if handler:
            logger.info(f"[Bootstrap] Processing simulated '{topic}' message")
            try:
                handler(msg)
            except Exception as e:
                logger.error(f"[Bootstrap] Simulated handler failed: {e}")

    if event_pub:
        logger.info("Subscribing worker to topics...")
        running = True
        
        def handle_stop(signum, frame):
            nonlocal running
            running = False

        import signal
        try:
            signal.signal(signal.SIGINT, handle_stop)
            signal.signal(signal.SIGTERM, handle_stop)
        except ValueError:
            pass

        def consumer_callback(payload: dict):
            event_type = payload.get("event_type")
            if not event_type:
                logger.warning(f"[Worker] Payload missing event_type: {payload}")
                return
            handler = TOPIC_HANDLERS.get(event_type)
            if handler:
                logger.info(f"[Worker] Dispatching local event '{event_type}'")
                try:
                    handler(payload)
                except Exception as exc:
                    logger.exception(f"[Worker] Event handling failed: {exc}")
            else:
                logger.warning(f"[Worker] No handler for event '{event_type}'")

        try:
            event_pub.start_consumer(
                topic=list(TOPIC_HANDLERS.keys()),
                group_id="agent-worker-group",
                callback=consumer_callback,
                stop_check=lambda: not running
            )
        except Exception as e:
            logger.error(f"Worker consumer loop failed: {e}")
    else:
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Shutting down Agent Worker Pool.")


if __name__ == "__main__":
    main()

