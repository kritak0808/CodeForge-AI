from typing import List
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import settings
from app.database import get_db
from app.repositories.user import UserRepository
from app.repositories.project import ProjectRepository
from app.services.user import UserService
from app.services.project import ProjectService
from app.schemas.token import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

def get_project_repository(db: AsyncSession = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(db)

def get_user_service(repository: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repository)

def get_project_service(repository: ProjectRepository = Depends(get_project_repository)) -> ProjectService:
    return ProjectService(repository)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")
        if username is None or user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1.0,
            socket_timeout=1.0
        )
        token_revoked = await r.get(f"blacklist:{token[-30:]}")
        user_revoked = await r.get(f"user_revoked:{username}")
        await r.close()
        
        if token_revoked or user_revoked:
            raise credentials_exception
    except HTTPException:
        raise
    except Exception:
        pass

    return TokenData(username=username, role=role, scopes=[user_id])

class RoleRequired:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )
        return current_user

# --- Enterprise DI Mappings ---
from app.repositories.enterprise import ApiKeyRepository, AuditEventRepository, FeatureFlagRepository
from app.services.enterprise import ApiKeyService, AuditService, FeatureFlagService

def get_api_key_repository(db: AsyncSession = Depends(get_db)) -> ApiKeyRepository:
    return ApiKeyRepository(db)

def get_audit_repository(db: AsyncSession = Depends(get_db)) -> AuditEventRepository:
    return AuditEventRepository(db)

def get_flag_repository(db: AsyncSession = Depends(get_db)) -> FeatureFlagRepository:
    return FeatureFlagRepository(db)

def get_api_key_service(repository: ApiKeyRepository = Depends(get_api_key_repository)) -> ApiKeyService:
    return ApiKeyService(repository)

def get_audit_service(repository: AuditEventRepository = Depends(get_audit_repository)) -> AuditService:
    return AuditService(repository)

def get_flag_service(repository: FeatureFlagRepository = Depends(get_flag_repository)) -> FeatureFlagService:
    return FeatureFlagService(repository)

# --- Workflow DI Mappings ---
from app.repositories.workflow import WorkflowRepository, WorkflowStateRepository, ApprovalRepository, TaskRepository
from app.services.workflow import WorkflowService

def get_workflow_repository(db: AsyncSession = Depends(get_db)) -> WorkflowRepository:
    return WorkflowRepository(db)

def get_workflow_state_repository(db: AsyncSession = Depends(get_db)) -> WorkflowStateRepository:
    return WorkflowStateRepository(db)

def get_approval_repository(db: AsyncSession = Depends(get_db)) -> ApprovalRepository:
    return ApprovalRepository(db)

def get_task_repository(db: AsyncSession = Depends(get_db)) -> TaskRepository:
    return TaskRepository(db)

def get_workflow_service(
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    approval_repo: ApprovalRepository = Depends(get_approval_repository),
    state_repo: WorkflowStateRepository = Depends(get_workflow_state_repository)
) -> WorkflowService:
    return WorkflowService(workflow_repo, approval_repo, state_repo)


# --- Database Agent DI Mappings (Milestone 7) ---
from app.repositories.database import (
    DatabaseDesignRepository,
    DatabaseEntityRepository,
    DatabaseRelationshipRepository,
    DatabaseIndexRepository,
    MigrationPlanRepository,
    QueryOptimizationRepository,
)
from app.services.database import DatabaseDesignService


def get_database_design_repository(db: AsyncSession = Depends(get_db)) -> DatabaseDesignRepository:
    return DatabaseDesignRepository(db)

def get_database_entity_repository(db: AsyncSession = Depends(get_db)) -> DatabaseEntityRepository:
    return DatabaseEntityRepository(db)

def get_database_relationship_repository(db: AsyncSession = Depends(get_db)) -> DatabaseRelationshipRepository:
    return DatabaseRelationshipRepository(db)

def get_database_index_repository(db: AsyncSession = Depends(get_db)) -> DatabaseIndexRepository:
    return DatabaseIndexRepository(db)

def get_migration_plan_repository(db: AsyncSession = Depends(get_db)) -> MigrationPlanRepository:
    return MigrationPlanRepository(db)

def get_query_optimization_repository(db: AsyncSession = Depends(get_db)) -> QueryOptimizationRepository:
    return QueryOptimizationRepository(db)

def get_database_design_service(
    db: AsyncSession = Depends(get_db),
    design_repo: DatabaseDesignRepository = Depends(get_database_design_repository),
    entity_repo: DatabaseEntityRepository = Depends(get_database_entity_repository),
    relationship_repo: DatabaseRelationshipRepository = Depends(get_database_relationship_repository),
    index_repo: DatabaseIndexRepository = Depends(get_database_index_repository),
    migration_repo: MigrationPlanRepository = Depends(get_migration_plan_repository),
    optimization_repo: QueryOptimizationRepository = Depends(get_query_optimization_repository),
) -> DatabaseDesignService:
    return DatabaseDesignService(
        design_repo=design_repo,
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        index_repo=index_repo,
        migration_repo=migration_repo,
        optimization_repo=optimization_repo,
        db=db,
    )


# --- Backend Agent DI Mappings (Milestone 8) ---
from app.repositories.backend import (
    BackendGenerationRepository,
    ApiEndpointRepository,
    ServiceDefinitionRepository,
    RepositoryDefinitionRepository,
    BusinessRuleRepository,
    ApiTestReportRepository,
)
from app.services.backend import BackendGenerationService


def get_backend_generation_repository(db: AsyncSession = Depends(get_db)) -> BackendGenerationRepository:
    return BackendGenerationRepository(db)

def get_api_endpoint_repository(db: AsyncSession = Depends(get_db)) -> ApiEndpointRepository:
    return ApiEndpointRepository(db)

def get_service_definition_repository(db: AsyncSession = Depends(get_db)) -> ServiceDefinitionRepository:
    return ServiceDefinitionRepository(db)

def get_repository_definition_repository(db: AsyncSession = Depends(get_db)) -> RepositoryDefinitionRepository:
    return RepositoryDefinitionRepository(db)

def get_business_rule_repository(db: AsyncSession = Depends(get_db)) -> BusinessRuleRepository:
    return BusinessRuleRepository(db)

def get_api_test_report_repository(db: AsyncSession = Depends(get_db)) -> ApiTestReportRepository:
    return ApiTestReportRepository(db)

def get_backend_generation_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: BackendGenerationRepository = Depends(get_backend_generation_repository),
    endpoint_repo: ApiEndpointRepository = Depends(get_api_endpoint_repository),
    service_repo: ServiceDefinitionRepository = Depends(get_service_definition_repository),
    repository_repo: RepositoryDefinitionRepository = Depends(get_repository_definition_repository),
    rule_repo: BusinessRuleRepository = Depends(get_business_rule_repository),
    test_repo: ApiTestReportRepository = Depends(get_api_test_report_repository),
) -> BackendGenerationService:
    return BackendGenerationService(
        generation_repo=generation_repo,
        endpoint_repo=endpoint_repo,
        service_repo=service_repo,
        repository_repo=repository_repo,
        rule_repo=rule_repo,
        test_repo=test_repo,
        db=db,
    )


# --- Frontend Agent DI Mappings (Milestone 9) ---
from app.repositories.frontend import (
    FrontendGenerationRepository,
    FrontendPageRepository,
    FrontendComponentRepository,
    FrontendFormRepository,
    FrontendHookRepository,
    FrontendTestReportRepository,
    UiDesignArtifactRepository,
)
from app.services.frontend import FrontendGenerationService


def get_frontend_generation_repository(db: AsyncSession = Depends(get_db)) -> FrontendGenerationRepository:
    return FrontendGenerationRepository(db)

def get_frontend_page_repository(db: AsyncSession = Depends(get_db)) -> FrontendPageRepository:
    return FrontendPageRepository(db)

def get_frontend_component_repository(db: AsyncSession = Depends(get_db)) -> FrontendComponentRepository:
    return FrontendComponentRepository(db)

def get_frontend_form_repository(db: AsyncSession = Depends(get_db)) -> FrontendFormRepository:
    return FrontendFormRepository(db)

def get_frontend_hook_repository(db: AsyncSession = Depends(get_db)) -> FrontendHookRepository:
    return FrontendHookRepository(db)

def get_frontend_test_report_repository(db: AsyncSession = Depends(get_db)) -> FrontendTestReportRepository:
    return FrontendTestReportRepository(db)

def get_ui_design_artifact_repository(db: AsyncSession = Depends(get_db)) -> UiDesignArtifactRepository:
    return UiDesignArtifactRepository(db)

def get_frontend_generation_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: FrontendGenerationRepository = Depends(get_frontend_generation_repository),
    page_repo: FrontendPageRepository = Depends(get_frontend_page_repository),
    component_repo: FrontendComponentRepository = Depends(get_frontend_component_repository),
    form_repo: FrontendFormRepository = Depends(get_frontend_form_repository),
    hook_repo: FrontendHookRepository = Depends(get_frontend_hook_repository),
    test_repo: FrontendTestReportRepository = Depends(get_frontend_test_report_repository),
    ui_design_artifact_repo: UiDesignArtifactRepository = Depends(get_ui_design_artifact_repository),
) -> FrontendGenerationService:
    return FrontendGenerationService(
        generation_repo=generation_repo,
        page_repo=page_repo,
        component_repo=component_repo,
        form_repo=form_repo,
        hook_repo=hook_repo,
        test_repo=test_repo,
        ui_design_artifact_repo=ui_design_artifact_repo,
        db=db,
    )


# --- QA Agent DI Mappings (Milestone 10) ---
from app.repositories.qa import (
    QaGenerationRepository,
    QaTestSuiteRepository,
    QaTestCaseRepository,
    QaTestRunRepository,
    QaBugReportRepository,
    QaCoverageReportRepository,
    QaQualityMetricsRepository,
)
from app.services.qa import QaGenerationService


def get_qa_generation_repository(db: AsyncSession = Depends(get_db)) -> QaGenerationRepository:
    return QaGenerationRepository(db)

def get_qa_test_suite_repository(db: AsyncSession = Depends(get_db)) -> QaTestSuiteRepository:
    return QaTestSuiteRepository(db)

def get_qa_test_case_repository(db: AsyncSession = Depends(get_db)) -> QaTestCaseRepository:
    return QaTestCaseRepository(db)

def get_qa_test_run_repository(db: AsyncSession = Depends(get_db)) -> QaTestRunRepository:
    return QaTestRunRepository(db)

def get_qa_bug_report_repository(db: AsyncSession = Depends(get_db)) -> QaBugReportRepository:
    return QaBugReportRepository(db)

def get_qa_coverage_report_repository(db: AsyncSession = Depends(get_db)) -> QaCoverageReportRepository:
    return QaCoverageReportRepository(db)

def get_qa_quality_metrics_repository(db: AsyncSession = Depends(get_db)) -> QaQualityMetricsRepository:
    return QaQualityMetricsRepository(db)

def get_qa_generation_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: QaGenerationRepository = Depends(get_qa_generation_repository),
    suite_repo: QaTestSuiteRepository = Depends(get_qa_test_suite_repository),
    case_repo: QaTestCaseRepository = Depends(get_qa_test_case_repository),
    run_repo: QaTestRunRepository = Depends(get_qa_test_run_repository),
    bug_repo: QaBugReportRepository = Depends(get_qa_bug_report_repository),
    coverage_repo: QaCoverageReportRepository = Depends(get_qa_coverage_report_repository),
    metrics_repo: QaQualityMetricsRepository = Depends(get_qa_quality_metrics_repository),
) -> QaGenerationService:
    return QaGenerationService(
        generation_repo=generation_repo,
        suite_repo=suite_repo,
        case_repo=case_repo,
        run_repo=run_repo,
        bug_repo=bug_repo,
        coverage_repo=coverage_repo,
        metrics_repo=metrics_repo,
        db=db,
    )


# --- Security Agent DI Mappings (Milestone 11) ---
from app.repositories.security import (
    SecurityGenerationRepository,
    ThreatModelRepository,
    SecurityFindingRepository,
    DependencyScanRepository,
    SecretScanRepository,
    RbacAuditRepository,
    SecurityReportRepository,
)
from app.services.security import SecurityGenerationService


def get_security_generation_repository(db: AsyncSession = Depends(get_db)) -> SecurityGenerationRepository:
    return SecurityGenerationRepository(db)

def get_threat_model_repository(db: AsyncSession = Depends(get_db)) -> ThreatModelRepository:
    return ThreatModelRepository(db)

def get_security_finding_repository(db: AsyncSession = Depends(get_db)) -> SecurityFindingRepository:
    return SecurityFindingRepository(db)

def get_dependency_scan_repository(db: AsyncSession = Depends(get_db)) -> DependencyScanRepository:
    return DependencyScanRepository(db)

def get_secret_scan_repository(db: AsyncSession = Depends(get_db)) -> SecretScanRepository:
    return SecretScanRepository(db)

def get_rbac_audit_repository(db: AsyncSession = Depends(get_db)) -> RbacAuditRepository:
    return RbacAuditRepository(db)

def get_security_report_repository(db: AsyncSession = Depends(get_db)) -> SecurityReportRepository:
    return SecurityReportRepository(db)

def get_security_generation_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: SecurityGenerationRepository = Depends(get_security_generation_repository),
    threat_model_repo: ThreatModelRepository = Depends(get_threat_model_repository),
    finding_repo: SecurityFindingRepository = Depends(get_security_finding_repository),
    dependency_repo: DependencyScanRepository = Depends(get_dependency_scan_repository),
    secret_repo: SecretScanRepository = Depends(get_secret_scan_repository),
    rbac_repo: RbacAuditRepository = Depends(get_rbac_audit_repository),
    report_repo: SecurityReportRepository = Depends(get_security_report_repository),
) -> SecurityGenerationService:
    return SecurityGenerationService(
        generation_repo=generation_repo,
        threat_model_repo=threat_model_repo,
        finding_repo=finding_repo,
        dependency_repo=dependency_repo,
        secret_repo=secret_repo,
        rbac_repo=rbac_repo,
        report_repo=report_repo,
        db=db,
    )


# --- DevOps Agent DI Mappings (Milestone 12) ---
from app.repositories.devops import (
    DevopsGenerationRepository,
    DockerArtifactRepository,
    KubernetesArtifactRepository,
    HelmArtifactRepository,
    TerraformArtifactRepository,
    CicdPipelineRepository,
    DeploymentTemplateRepository,
)
from app.services.devops import DevOpsGenerationService


def get_devops_generation_repository(db: AsyncSession = Depends(get_db)) -> DevopsGenerationRepository:
    return DevopsGenerationRepository(db)

def get_docker_artifact_repository(db: AsyncSession = Depends(get_db)) -> DockerArtifactRepository:
    return DockerArtifactRepository(db)

def get_kubernetes_artifact_repository(db: AsyncSession = Depends(get_db)) -> KubernetesArtifactRepository:
    return KubernetesArtifactRepository(db)

def get_helm_artifact_repository(db: AsyncSession = Depends(get_db)) -> HelmArtifactRepository:
    return HelmArtifactRepository(db)

def get_terraform_artifact_repository(db: AsyncSession = Depends(get_db)) -> TerraformArtifactRepository:
    return TerraformArtifactRepository(db)

def get_cicd_pipeline_repository(db: AsyncSession = Depends(get_db)) -> CicdPipelineRepository:
    return CicdPipelineRepository(db)

def get_deployment_template_repository(db: AsyncSession = Depends(get_db)) -> DeploymentTemplateRepository:
    return DeploymentTemplateRepository(db)

def get_devops_generation_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: DevopsGenerationRepository = Depends(get_devops_generation_repository),
    docker_repo: DockerArtifactRepository = Depends(get_docker_artifact_repository),
    kubernetes_repo: KubernetesArtifactRepository = Depends(get_kubernetes_artifact_repository),
    helm_repo: HelmArtifactRepository = Depends(get_helm_artifact_repository),
    terraform_repo: TerraformArtifactRepository = Depends(get_terraform_artifact_repository),
    pipeline_repo: CicdPipelineRepository = Depends(get_cicd_pipeline_repository),
    template_repo: DeploymentTemplateRepository = Depends(get_deployment_template_repository),
) -> DevOpsGenerationService:
    return DevOpsGenerationService(
        generation_repo=generation_repo,
        docker_repo=docker_repo,
        kubernetes_repo=kubernetes_repo,
        helm_repo=helm_repo,
        terraform_repo=terraform_repo,
        pipeline_repo=pipeline_repo,
        template_repo=template_repo,
        db=db,
    )



# ── MILESTONE 14 – Collaboration Engine Dependencies ─────────────────────────

from app.repositories.collaboration import (
    AgentCollaborationSessionRepository,
    AgentConversationRepository,
    AgentMessageRepository,
    AgentReviewRepository,
    AgentVoteRepository,
    AgentConflictRepository,
    AgentResolutionRepository,
)
from app.services.collaboration import CollaborationService


def get_collaboration_session_repository(db: AsyncSession = Depends(get_db)) -> AgentCollaborationSessionRepository:
    return AgentCollaborationSessionRepository(db)

def get_conversation_repository(db: AsyncSession = Depends(get_db)) -> AgentConversationRepository:
    return AgentConversationRepository(db)

def get_message_repository(db: AsyncSession = Depends(get_db)) -> AgentMessageRepository:
    return AgentMessageRepository(db)

def get_review_repository(db: AsyncSession = Depends(get_db)) -> AgentReviewRepository:
    return AgentReviewRepository(db)

def get_vote_repository(db: AsyncSession = Depends(get_db)) -> AgentVoteRepository:
    return AgentVoteRepository(db)

def get_conflict_repository(db: AsyncSession = Depends(get_db)) -> AgentConflictRepository:
    return AgentConflictRepository(db)

def get_resolution_repository(db: AsyncSession = Depends(get_db)) -> AgentResolutionRepository:
    return AgentResolutionRepository(db)

def get_collaboration_service(
    db: AsyncSession = Depends(get_db),
    session_repo: AgentCollaborationSessionRepository = Depends(get_collaboration_session_repository),
    conversation_repo: AgentConversationRepository = Depends(get_conversation_repository),
    message_repo: AgentMessageRepository = Depends(get_message_repository),
    review_repo: AgentReviewRepository = Depends(get_review_repository),
    vote_repo: AgentVoteRepository = Depends(get_vote_repository),
    conflict_repo: AgentConflictRepository = Depends(get_conflict_repository),
    resolution_repo: AgentResolutionRepository = Depends(get_resolution_repository),
) -> CollaborationService:
    return CollaborationService(
        session_repo=session_repo,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        review_repo=review_repo,
        vote_repo=vote_repo,
        conflict_repo=conflict_repo,
        resolution_repo=resolution_repo,
        db=db,
    )


# ── MILESTONE 15 – Observability & Monitoring Platform Dependencies ───────────

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
from app.services.observability import ObservabilityService


def get_observability_generation_repository(
    db: AsyncSession = Depends(get_db),
) -> ObservabilityGenerationRepository:
    return ObservabilityGenerationRepository(db)


def get_agent_metric_repository(
    db: AsyncSession = Depends(get_db),
) -> AgentMetricRepository:
    return AgentMetricRepository(db)


def get_workflow_metric_repository(
    db: AsyncSession = Depends(get_db),
) -> WorkflowMetricRepository:
    return WorkflowMetricRepository(db)


def get_api_metric_repository(
    db: AsyncSession = Depends(get_db),
) -> ApiMetricRepository:
    return ApiMetricRepository(db)


def get_system_metric_repository(
    db: AsyncSession = Depends(get_db),
) -> SystemMetricRepository:
    return SystemMetricRepository(db)


def get_error_event_repository(
    db: AsyncSession = Depends(get_db),
) -> ErrorEventRepository:
    return ErrorEventRepository(db)


def get_alert_rule_repository(
    db: AsyncSession = Depends(get_db),
) -> AlertRuleRepository:
    return AlertRuleRepository(db)


def get_alert_event_repository(
    db: AsyncSession = Depends(get_db),
) -> AlertEventRepository:
    return AlertEventRepository(db)


def get_observability_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: ObservabilityGenerationRepository = Depends(get_observability_generation_repository),
    agent_metric_repo: AgentMetricRepository = Depends(get_agent_metric_repository),
    workflow_metric_repo: WorkflowMetricRepository = Depends(get_workflow_metric_repository),
    api_metric_repo: ApiMetricRepository = Depends(get_api_metric_repository),
    system_metric_repo: SystemMetricRepository = Depends(get_system_metric_repository),
    error_event_repo: ErrorEventRepository = Depends(get_error_event_repository),
    alert_rule_repo: AlertRuleRepository = Depends(get_alert_rule_repository),
    alert_event_repo: AlertEventRepository = Depends(get_alert_event_repository),
) -> ObservabilityService:
    return ObservabilityService(
        generation_repo=generation_repo,
        agent_metric_repo=agent_metric_repo,
        workflow_metric_repo=workflow_metric_repo,
        api_metric_repo=api_metric_repo,
        system_metric_repo=system_metric_repo,
        error_event_repo=error_event_repo,
        alert_rule_repo=alert_rule_repo,
        alert_event_repo=alert_event_repo,
        db=db,
    )


# ── MILESTONE 16 – Cost Optimization Agent Dependencies ───────────────────────

from app.repositories.cost import (
    CostGenerationRepository,
    CostReportRepository,
    ResourceUsageMetricRepository,
    OptimizationRecommendationRepository,
    SavingsEstimateRepository,
    BudgetPolicyRepository,
    CostAlertRepository,
)
from app.services.cost import CostOptimizationService


def get_cost_generation_repository(
    db: AsyncSession = Depends(get_db),
) -> CostGenerationRepository:
    return CostGenerationRepository(db)


def get_cost_report_repository(
    db: AsyncSession = Depends(get_db),
) -> CostReportRepository:
    return CostReportRepository(db)


def get_resource_usage_metric_repository(
    db: AsyncSession = Depends(get_db),
) -> ResourceUsageMetricRepository:
    return ResourceUsageMetricRepository(db)


def get_optimization_recommendation_repository(
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationRepository:
    return OptimizationRecommendationRepository(db)


def get_savings_estimate_repository(
    db: AsyncSession = Depends(get_db),
) -> SavingsEstimateRepository:
    return SavingsEstimateRepository(db)


def get_budget_policy_repository(
    db: AsyncSession = Depends(get_db),
) -> BudgetPolicyRepository:
    return BudgetPolicyRepository(db)


def get_cost_alert_repository(
    db: AsyncSession = Depends(get_db),
) -> CostAlertRepository:
    return CostAlertRepository(db)


def get_cost_optimization_service(
    db: AsyncSession = Depends(get_db),
    generation_repo: CostGenerationRepository = Depends(get_cost_generation_repository),
    report_repo: CostReportRepository = Depends(get_cost_report_repository),
    metric_repo: ResourceUsageMetricRepository = Depends(get_resource_usage_metric_repository),
    recommendation_repo: OptimizationRecommendationRepository = Depends(get_optimization_recommendation_repository),
    savings_repo: SavingsEstimateRepository = Depends(get_savings_estimate_repository),
    policy_repo: BudgetPolicyRepository = Depends(get_budget_policy_repository),
    alert_repo: CostAlertRepository = Depends(get_cost_alert_repository),
) -> CostOptimizationService:
    return CostOptimizationService(
        generation_repo=generation_repo,
        report_repo=report_repo,
        metric_repo=metric_repo,
        recommendation_repo=recommendation_repo,
        savings_repo=savings_repo,
        policy_repo=policy_repo,
        alert_repo=alert_repo,
        db=db,
    )


# ── MILESTONE 17 – Autonomous SDLC Controller Dependencies ───────────────────

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
from app.services.controller import AutonomousControllerService


def get_autonomous_controller_repository(
    db: AsyncSession = Depends(get_db),
) -> AutonomousControllerRepository:
    return AutonomousControllerRepository(db)


def get_workflow_decision_repository(
    db: AsyncSession = Depends(get_db),
) -> WorkflowDecisionRepository:
    return WorkflowDecisionRepository(db)


def get_agent_health_repository(
    db: AsyncSession = Depends(get_db),
) -> AgentHealthRepository:
    return AgentHealthRepository(db)


def get_retry_history_repository(
    db: AsyncSession = Depends(get_db),
) -> RetryHistoryRepository:
    return RetryHistoryRepository(db)


def get_failure_event_repository(
    db: AsyncSession = Depends(get_db),
) -> FailureEventRepository:
    return FailureEventRepository(db)


def get_rollback_event_repository(
    db: AsyncSession = Depends(get_db),
) -> RollbackEventRepository:
    return RollbackEventRepository(db)


def get_execution_plan_repository(
    db: AsyncSession = Depends(get_db),
) -> ExecutionPlanRepository:
    return ExecutionPlanRepository(db)


def get_controller_log_repository(
    db: AsyncSession = Depends(get_db),
) -> ControllerLogRepository:
    return ControllerLogRepository(db)


def get_autonomous_controller_service(
    db: AsyncSession = Depends(get_db),
    controller_repo: AutonomousControllerRepository = Depends(get_autonomous_controller_repository),
    decision_repo: WorkflowDecisionRepository = Depends(get_workflow_decision_repository),
    health_repo: AgentHealthRepository = Depends(get_agent_health_repository),
    retry_repo: RetryHistoryRepository = Depends(get_retry_history_repository),
    failure_repo: FailureEventRepository = Depends(get_failure_event_repository),
    rollback_repo: RollbackEventRepository = Depends(get_rollback_event_repository),
    plan_repo: ExecutionPlanRepository = Depends(get_execution_plan_repository),
    log_repo: ControllerLogRepository = Depends(get_controller_log_repository),
) -> AutonomousControllerService:
    return AutonomousControllerService(
        controller_repo=controller_repo,
        decision_repo=decision_repo,
        health_repo=health_repo,
        retry_repo=retry_repo,
        failure_repo=failure_repo,
        rollback_repo=rollback_repo,
        plan_repo=plan_repo,
        log_repo=log_repo,
        db=db,
    )


