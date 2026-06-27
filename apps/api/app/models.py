import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Boolean, JSON, UUID, Integer, Float
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="developer")
    
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)

    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="user")
    workflows = relationship("Workflow", back_populates="trigger_user")
    approvals = relationship("Approval", back_populates="approver")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    project_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(String(1000), nullable=True)
    tech_stack = Column(JSON, nullable=False)
    repository_url = Column(String(500), nullable=True)
    budget_usd_limit = Column(Numeric(10, 2), nullable=False, default=50.00)

    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="projects")
    workflows = relationship("Workflow", back_populates="project", cascade="all, delete-orphan")
    agent_memories = relationship("AgentMemory", back_populates="project", cascade="all, delete-orphan")
    project_memories = relationship("ProjectMemory", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")

class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")

class ApiKey(Base):
    __tablename__ = "api_keys"

    api_key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    prefix = Column(String(8), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="audit_events")

class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    flag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=False)
    conditions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    role_description = Column(String(1000), nullable=False)
    llm_model = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tasks = relationship("Task", back_populates="agent")
    memories = relationship("AgentMemory", back_populates="agent")
    metrics = relationship("Metric", back_populates="agent")

class Workflow(Base):
    __tablename__ = "workflows"

    workflow_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    current_state = Column(String(50), nullable=False, default="CREATED")
    # Derived status field used by the frontend (CREATED/RUNNING/PAUSED/FAILED/COMPLETED)
    status = Column(String(50), nullable=False, default="CREATED", index=True)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_total = Column(Integer, nullable=False, default=0)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="workflows")
    trigger_user = relationship("User", back_populates="workflows")
    states = relationship("WorkflowState", back_populates="workflow", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="workflow", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="workflow", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="workflow", cascade="all, delete-orphan")

class WorkflowState(Base):
    __tablename__ = "workflow_states"

    state_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(String(50), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    entered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    exited_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="states")

class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(50), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    status = Column(String(50), nullable=False, default="TODO")
    depends_on = Column(JSON, nullable=True)  # Stored as list of strings/UUIDs for compatibility
    assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="tasks")
    agent = relationship("Agent", back_populates="tasks")

class AgentMemory(Base):
    __tablename__ = "agent_memory"

    memory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(50), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)  # ShortTerm, LongTerm, Semantic
    content = Column(String(5000), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    agent = relationship("Agent", back_populates="memories")
    project = relationship("Project", back_populates="agent_memories")

class ProjectMemory(Base):
    __tablename__ = "project_memory"

    project_memory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(100), nullable=False, index=True)
    val_data = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="project_memories")

class Approval(Base):
    __tablename__ = "approvals"

    approval_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    approval_type = Column(String(100), nullable=False)  # Architecture, Database, Security, Deployment
    status = Column(String(50), nullable=False, default="PENDING")
    artifact_payload = Column(JSON, nullable=False)
    comments = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="approvals")
    approver = relationship("User", back_populates="approvals")

class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    url = Column(String(500), nullable=False)
    tech_tag = Column(String(50), nullable=False, index=True)
    last_crawled_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    documents = relationship("Document", back_populates="source", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_sources.source_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content_path = Column(String(500), nullable=False)
    hash = Column(String(64), nullable=False)

    source = relationship("KnowledgeSource", back_populates="documents")
    embeddings = relationship("Embedding", back_populates="document", cascade="all, delete-orphan")

class Embedding(Base):
    __tablename__ = "embeddings"

    embedding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    vector_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # ID mapped to Qdrant vector
    chunk_index = Column(Integer, nullable=False)
    metadata_json = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="embeddings")

class Deployment(Base):
    __tablename__ = "deployments"

    deployment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(50), nullable=False)  # staging, production
    status = Column(String(50), nullable=False)  # provisioning, active, rolled_back, failed
    live_url = Column(String(500), nullable=True)
    k8s_namespace = Column(String(100), nullable=False)
    commit_sha = Column(String(40), nullable=True)
    deployed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="deployments")

class Metric(Base):
    __tablename__ = "metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(50), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    tokens_consumed = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    workflow = relationship("Workflow", back_populates="metrics")
    agent = relationship("Agent", back_populates="metrics")

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(String(2000), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")

class ApprovalPolicy(Base):
    __tablename__ = "approval_policies"

    policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    action_type = Column(String(100), nullable=False, index=True)  # e.g., Architecture, Deployment, Budget
    required_role = Column(String(50), nullable=False)  # e.g., Senior Engineer, Admin, Finance
    min_approvers = Column(Integer, nullable=False, default=1)
    timeout_hours = Column(Integer, nullable=False, default=24)
    budget_limit = Column(Numeric(10, 2), nullable=True)

    requests = relationship("ApprovalRequest", back_populates="policy")

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    approval_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    approval_type = Column(String(100), nullable=False)  # Architecture, Database, Technology, Security, Deployment, Budget, Emergency
    status = Column(String(50), nullable=False, default="WAITING_FOR_APPROVAL")  # WAITING_FOR_APPROVAL, APPROVED, REJECTED, REWORK_REQUIRED, EXPIRED, ESCALATED
    policy_id = Column(UUID(as_uuid=True), ForeignKey("approval_policies.policy_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    workflow = relationship("Workflow")
    policy = relationship("ApprovalPolicy", back_populates="requests")
    responses = relationship("ApprovalResponse", back_populates="request", cascade="all, delete-orphan")
    escalations = relationship("ApprovalEscalation", back_populates="request", cascade="all, delete-orphan")
    notifications = relationship("ApprovalNotification", back_populates="request", cascade="all, delete-orphan")

class ApprovalResponse(Base):
    __tablename__ = "approval_responses"

    response_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.approval_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    decision = Column(String(50), nullable=False)  # APPROVED, REJECTED, REWORK
    comments = Column(String(1000), nullable=True)
    signature = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    request = relationship("ApprovalRequest", back_populates="responses")
    user = relationship("User")

class ApprovalEscalation(Base):
    __tablename__ = "approval_escalations"

    escalation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.approval_id", ondelete="CASCADE"), nullable=False, index=True)
    escalation_role = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, ESCALATED, RESOLVED
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    escalated_at = Column(DateTime(timezone=True), nullable=True)

    request = relationship("ApprovalRequest", back_populates="escalations")

class ApprovalNotification(Base):
    __tablename__ = "approval_notifications"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.approval_id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)  # Email, Slack, SSE, Dashboard
    status = Column(String(50), nullable=False, default="SENT")  # SENT, FAILED
    message = Column(String(2000), nullable=False)
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    request = relationship("ApprovalRequest", back_populates="notifications")

class ApprovalAuditLog(Base):
    __tablename__ = "approval_audit_log"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(50), nullable=True)
    reason = Column(String(1000), nullable=True)
    decision = Column(String(50), nullable=False)
    signature = Column(String(500), nullable=True)

    actor = relationship("User")
    workflow = relationship("Workflow")

class ArchitectureReport(Base):
    __tablename__ = "architecture_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    requirements = Column(String, nullable=False)
    report_text = Column(String, nullable=False)
    complexity_score = Column(Integer, nullable=False, default=1)
    estimated_cost = Column(Numeric(10, 2), nullable=False, default=0.00)
    risk_assessment = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    workflow = relationship("Workflow")
    project = relationship("Project")
    decisions = relationship("ArchitectureDecision", back_populates="report", cascade="all, delete-orphan")
    recommendations = relationship("TechnologyRecommendation", back_populates="report", cascade="all, delete-orphan")
    reviews = relationship("ArchitectureReview", back_populates="report", cascade="all, delete-orphan")

class ArchitectureDecision(Base):
    __tablename__ = "architecture_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("architecture_reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=False)
    status = Column(String(50), nullable=False, default="PROPOSED")  # PROPOSED, ACCEPTED, REJECTED
    rationale = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    report = relationship("ArchitectureReport", back_populates="decisions")

class TechnologyRecommendation(Base):
    __tablename__ = "technology_recommendations"

    recommendation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("architecture_reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)  # frontend, backend, database, deployment
    technology_name = Column(String(100), nullable=False)
    version_spec = Column(String(50), nullable=False)
    suitability_reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    report = relationship("ArchitectureReport", back_populates="recommendations")

class ArchitectureReview(Base):
    __tablename__ = "architecture_reviews"

    review_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("architecture_reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    decision = Column(String(50), nullable=False)  # APPROVED, REWORK_REQUIRED, REJECTED
    comments = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    report = relationship("ArchitectureReport", back_populates="reviews")
    reviewer = relationship("User")


# ────────────────────────────────────────────────────────────────────────────
# MILESTONE 7 – Database Agent Models
# ────────────────────────────────────────────────────────────────────────────

class DatabaseDesign(Base):
    """Root design record produced by the DatabaseAgent."""
    __tablename__ = "database_designs"

    design_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Design status: GENERATING | COMPLETED | FAILED | SUPERSEDED
    status = Column(String(50), nullable=False, default="GENERATING")
    # Full SQL DDL for all entities (concatenated)
    sql_schema = Column(String, nullable=True)
    # ASCII + PlantUML ER diagram text
    er_diagram_text = Column(String, nullable=True)
    # Mermaid ER diagram for the dashboard
    er_diagram_mermaid = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    architecture_report = relationship("ArchitectureReport")
    workflow = relationship("Workflow")
    project = relationship("Project")
    entities = relationship(
        "DatabaseEntity", back_populates="design", cascade="all, delete-orphan"
    )
    relationships = relationship(
        "DatabaseRelationship", back_populates="design", cascade="all, delete-orphan"
    )
    indexes = relationship(
        "DatabaseIndex", back_populates="design", cascade="all, delete-orphan"
    )
    migration_plans = relationship(
        "MigrationPlan", back_populates="design", cascade="all, delete-orphan"
    )
    optimizations = relationship(
        "QueryOptimizationReport", back_populates="design", cascade="all, delete-orphan"
    )


class DatabaseEntity(Base):
    """Represents a single table/entity in the database design."""
    __tablename__ = "database_entities"

    entity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_name = Column(String(150), nullable=False)   # PascalCase model name
    table_name = Column(String(150), nullable=False)    # snake_case SQL table name
    description = Column(String(1000), nullable=True)
    # JSON array of column defs: [{name, type, nullable, default, comment}, ...]
    columns = Column(JSON, nullable=False, default=list)
    # JSON array of constraint defs: [{type, columns, references}, ...]
    constraints = Column(JSON, nullable=False, default=list)
    # Full CREATE TABLE DDL for this entity
    ddl = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("DatabaseDesign", back_populates="entities")


class DatabaseRelationship(Base):
    """FK / association relationship between two entities."""
    __tablename__ = "database_relationships"

    relationship_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_entity = Column(String(150), nullable=False)   # source table name
    to_entity = Column(String(150), nullable=False)     # target table name
    # ONE_TO_ONE | ONE_TO_MANY | MANY_TO_MANY
    relationship_type = Column(String(50), nullable=False)
    # e.g. "1:N", "M:N"
    cardinality = Column(String(20), nullable=False)
    # The FK column(s) that implement this relationship
    join_key = Column(String(255), nullable=False)
    # Extra notes (e.g. "via junction table order_items")
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("DatabaseDesign", back_populates="relationships")


class DatabaseIndex(Base):
    """Index recommendation produced by the agent's index advisor."""
    __tablename__ = "database_indexes"

    index_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_name = Column(String(150), nullable=False)
    index_name = Column(String(150), nullable=False)
    # JSON array of column names covered by the index
    columns = Column(JSON, nullable=False, default=list)
    # BTREE | HASH | GIN | GIST | BRIN
    index_type = Column(String(20), nullable=False, default="BTREE")
    # Is this a unique index?
    is_unique = Column(Boolean, nullable=False, default=False)
    # Partial index WHERE clause (optional)
    partial_where = Column(String(255), nullable=True)
    # DDL for the index
    ddl = Column(String(500), nullable=True)
    rationale = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("DatabaseDesign", back_populates="indexes")


class MigrationPlan(Base):
    """Alembic migration plan generated by the agent."""
    __tablename__ = "migration_plans"

    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # e.g. "20240101_001"
    migration_version = Column(String(50), nullable=False)
    # Full Alembic upgrade() script content
    migration_script = Column(String, nullable=False)
    # Full Alembic downgrade() script content
    rollback_script = Column(String, nullable=False)
    # DRAFT | READY | APPLIED | ROLLED_BACK
    status = Column(String(50), nullable=False, default="DRAFT")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    design = relationship("DatabaseDesign", back_populates="migration_plans")


class QueryOptimizationReport(Base):
    """Individual query optimization recommendation from the agent."""
    __tablename__ = "query_optimization_reports"

    optimization_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Short description of the problem: "N+1 on user.orders join"
    problem_statement = Column(String(500), nullable=False)
    # Detailed recommendation with example SQL
    recommendation = Column(String, nullable=False)
    # HIGH | MEDIUM | LOW
    priority = Column(String(20), nullable=False, default="MEDIUM")
    # e.g. "~60% reduction in query time"
    estimated_speedup = Column(String(100), nullable=True)
    # Category: N+1 | MISSING_INDEX | FULL_TABLE_SCAN | CARTESIAN | LOCK_CONTENTION | OTHER
    category = Column(String(50), nullable=False, default="OTHER")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("DatabaseDesign", back_populates="optimizations")


# ── MILESTONE 8 – Backend Agent Models ───────────────────────────────────────


class BackendGeneration(Base):
    """
    Root record for a Backend Agent generation run.

    Captures the full output of the BackendAgent pipeline for a specific
    workflow+project. Child records hold individual artifact types.
    """
    __tablename__ = "backend_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Link to the DatabaseDesign that was the input
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Link to the ArchitectureReport that was the input
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # PENDING | COMPLETED | FAILED | SUPERSEDED
    status = Column(String(50), nullable=False, default="PENDING")
    # Target framework: FastAPI, Django, Flask, etc.
    framework = Column(String(50), nullable=False, default="FastAPI")
    # Target language
    language = Column(String(20), nullable=False, default="Python")
    # Full assembled OpenAPI 3.1 YAML/JSON specification
    openapi_spec = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    endpoints = relationship(
        "ApiEndpoint", back_populates="generation", cascade="all, delete-orphan"
    )
    services = relationship(
        "ServiceDefinition", back_populates="generation", cascade="all, delete-orphan"
    )
    repositories = relationship(
        "RepositoryDefinition", back_populates="generation", cascade="all, delete-orphan"
    )
    rules = relationship(
        "BusinessRule", back_populates="generation", cascade="all, delete-orphan"
    )
    test_reports = relationship(
        "ApiTestReport", back_populates="generation", cascade="all, delete-orphan"
    )


class ApiEndpoint(Base):
    """
    A single API endpoint generated by the Backend Agent.

    Captures method, path, request/response schemas, and auth requirements
    for one generated FastAPI route.
    """
    __tablename__ = "api_endpoints"

    endpoint_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # HTTP method: GET | POST | PUT | PATCH | DELETE
    method = Column(String(10), nullable=False)
    # e.g. /api/v1/users/{user_id}
    path = Column(String(500), nullable=False)
    summary = Column(String(255), nullable=True)
    # Pydantic request body schema as a code string
    request_schema = Column(String, nullable=True)
    # Pydantic response schema as a code string
    response_schema = Column(String, nullable=True)
    # Full FastAPI route handler code string
    router_code = Column(String, nullable=True)
    # Requires JWT authentication
    auth_required = Column(Boolean, nullable=False, default=True)
    # Subject to rate limiting
    rate_limited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("BackendGeneration", back_populates="endpoints")


class ServiceDefinition(Base):
    """
    Generated service class for a domain entity.

    Contains the full service class code implementing business logic
    for a specific entity (e.g. UserService, ProjectService).
    """
    __tablename__ = "service_definitions"

    service_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_name = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    # Full Python class code string
    code = Column(String, nullable=False)
    # Comma-separated list of direct dependencies (e.g. "UserRepository,EmailService")
    dependencies = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("BackendGeneration", back_populates="services")


class RepositoryDefinition(Base):
    """
    Generated async SQLAlchemy repository class for a domain entity.

    Contains the full repository class code implementing data access
    for a specific ORM model.
    """
    __tablename__ = "repository_definitions"

    repo_def_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_name = Column(String(150), nullable=False)
    # Associated SQLAlchemy model class name
    model_name = Column(String(150), nullable=False)
    # Full Python class code string
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("BackendGeneration", back_populates="repositories")


class BusinessRule(Base):
    """
    A specific business rule enforced within the generated service layer.

    Rules are categorized by type and include the code snippet that
    implements the enforcement logic.
    """
    __tablename__ = "business_rules"

    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    # VALIDATION | AUTHORIZATION | RATE_LIMIT | BUSINESS_LOGIC | AUDIT | NOTIFICATION
    rule_type = Column(String(50), nullable=False, default="BUSINESS_LOGIC")
    # Python code snippet implementing the rule
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("BackendGeneration", back_populates="rules")


class ApiTestReport(Base):
    """
    Generated pytest test case for a specific API endpoint or service.

    Contains complete, runnable test code generated by the
    test_generator_tool in the BackendAgent pipeline.
    """
    __tablename__ = "api_test_reports"

    test_report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # unit | integration | api | e2e
    test_type = Column(String(50), nullable=False, default="integration")
    test_name = Column(String(255), nullable=False)
    # Full pytest test function/class code string
    test_code = Column(String, nullable=False)
    # GENERATED | VALIDATED | FAILED
    status = Column(String(20), nullable=False, default="GENERATED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("BackendGeneration", back_populates="test_reports")


# ── MILESTONE 9 – Frontend Agent Models ──────────────────────────────────────


class FrontendGeneration(Base):
    """
    Root record for a Frontend Agent generation run.
    """
    __tablename__ = "frontend_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Link to the BackendGeneration that was the input
    backend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Link to the DatabaseDesign that was the input
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Link to the ArchitectureReport that was the input
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # PENDING | COMPLETED | FAILED | SUPERSEDED
    status = Column(String(50), nullable=False, default="PENDING")
    framework = Column(String(50), nullable=False, default="Next.js 15")
    language = Column(String(20), nullable=False, default="TypeScript")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    pages = relationship(
        "FrontendPage", back_populates="generation", cascade="all, delete-orphan"
    )
    components = relationship(
        "FrontendComponent", back_populates="generation", cascade="all, delete-orphan"
    )
    forms = relationship(
        "FrontendForm", back_populates="generation", cascade="all, delete-orphan"
    )
    hooks = relationship(
        "FrontendHook", back_populates="generation", cascade="all, delete-orphan"
    )
    test_reports = relationship(
        "FrontendTestReport", back_populates="generation", cascade="all, delete-orphan"
    )
    ui_design_artifacts = relationship(
        "UiDesignArtifact", back_populates="generation", cascade="all, delete-orphan"
    )


class FrontendPage(Base):
    """
    A single Next.js page generated by the Frontend Agent.
    """
    __tablename__ = "frontend_pages"

    page_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_type = Column(String(50), nullable=False)
    route_path = Column(String(500), nullable=False)
    code = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="pages")


class FrontendComponent(Base):
    """
    A generated ShadCN component.
    """
    __tablename__ = "frontend_components"

    component_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_name = Column(String(150), nullable=False)
    component_type = Column(String(50), nullable=False)
    code = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="components")


class FrontendForm(Base):
    """
    A generated React Hook Form with Zod validation.
    """
    __tablename__ = "frontend_forms"

    form_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    form_name = Column(String(150), nullable=False)
    fields_schema = Column(JSON, nullable=True)
    validation_schema = Column(String, nullable=True)
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="forms")


class FrontendHook(Base):
    """
    A generated React Query hook or state hook.
    """
    __tablename__ = "frontend_hooks"

    hook_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hook_name = Column(String(150), nullable=False)
    hook_type = Column(String(50), nullable=False)
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="hooks")


class FrontendTestReport(Base):
    """
    Generated frontend tests for the Next.js pages/components.
    """
    __tablename__ = "frontend_test_reports"

    test_report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_type = Column(String(50), nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default="GENERATED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="test_reports")


class UiDesignArtifact(Base):
    """
    UI Design system, theme config, or layouts.
    """
    __tablename__ = "ui_design_artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_name = Column(String(150), nullable=False)
    artifact_type = Column(String(50), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("FrontendGeneration", back_populates="ui_design_artifacts")


# ── MILESTONE 10 – QA Agent Models ──────────────────────────────────────────


class QaGeneration(Base):
    """
    Root record for a QA Agent generation run.
    """
    __tablename__ = "qa_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    frontend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="PENDING")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    test_suites = relationship(
        "QaTestSuite", back_populates="generation", cascade="all, delete-orphan"
    )
    test_cases = relationship(
        "QaTestCase", back_populates="generation", cascade="all, delete-orphan"
    )
    test_runs = relationship(
        "QaTestRun", back_populates="generation", cascade="all, delete-orphan"
    )
    bug_reports = relationship(
        "QaBugReport", back_populates="generation", cascade="all, delete-orphan"
    )
    coverage_reports = relationship(
        "QaCoverageReport", back_populates="generation", cascade="all, delete-orphan"
    )
    quality_metrics = relationship(
        "QaQualityMetrics", back_populates="generation", cascade="all, delete-orphan"
    )


class QaTestSuite(Base):
    """
    Automated test suite (pytest/playwright code).
    """
    __tablename__ = "qa_test_suites"

    suite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suite_name = Column(String(150), nullable=False)
    suite_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=True)
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="test_suites")
    test_cases = relationship("QaTestCase", back_populates="suite", cascade="all, delete-orphan")


class QaTestCase(Base):
    """
    Specific test case nested within a suite.
    """
    __tablename__ = "qa_test_cases"

    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suite_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_test_suites.suite_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    case_name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    test_code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="test_cases")
    suite = relationship("QaTestSuite", back_populates="test_cases")


class QaTestRun(Base):
    """
    QA Test Execution Run.
    """
    __tablename__ = "qa_test_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runner_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    summary_json = Column(JSON, nullable=True)
    stdout = Column(String, nullable=True)
    stderr = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="test_runs")


class QaBugReport(Base):
    """
    Detected bug report.
    """
    __tablename__ = "qa_bug_reports"

    bug_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)
    description = Column(String, nullable=False)
    steps_to_reproduce = Column(String, nullable=True)
    expected_behavior = Column(String, nullable=True)
    actual_behavior = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="bug_reports")


class QaCoverageReport(Base):
    """
    Coverage reports.
    """
    __tablename__ = "qa_coverage_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coverage_type = Column(String(50), nullable=False)
    line_coverage = Column(Float, nullable=False)
    branch_coverage = Column(Float, nullable=True)
    summary_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="coverage_reports")


class QaQualityMetrics(Base):
    """
    Quality metrics dashboard / scorecard.
    """
    __tablename__ = "qa_quality_metrics"

    metrics_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qa_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_score = Column(Float, nullable=False)
    reliability_score = Column(Float, nullable=True)
    security_score = Column(Float, nullable=True)
    maintainability_score = Column(Float, nullable=True)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("QaGeneration", back_populates="quality_metrics")


# ── MILESTONE 11 – Security Agent Models ────────────────────────────────────


class SecurityGeneration(Base):
    """
    Root record for a Security Agent generation run.
    """
    __tablename__ = "security_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    frontend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="PENDING")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    threat_models = relationship(
        "ThreatModel", back_populates="generation", cascade="all, delete-orphan"
    )
    security_findings = relationship(
        "SecurityFinding", back_populates="generation", cascade="all, delete-orphan"
    )
    dependency_scans = relationship(
        "DependencyScan", back_populates="generation", cascade="all, delete-orphan"
    )
    secret_scans = relationship(
        "SecretScan", back_populates="generation", cascade="all, delete-orphan"
    )
    rbac_audits = relationship(
        "RbacAudit", back_populates="generation", cascade="all, delete-orphan"
    )
    security_reports = relationship(
        "SecurityReport", back_populates="generation", cascade="all, delete-orphan"
    )


class ThreatModel(Base):
    """
    Threat models.
    """
    __tablename__ = "threat_models"

    model_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    threat_source = Column(String(150), nullable=False)
    vulnerability = Column(String(500), nullable=False)
    impact = Column(String(150), nullable=False)
    risk_level = Column(String(50), nullable=False)
    mitigation = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="threat_models")


class SecurityFinding(Base):
    """
    Individual security finding SAST/DAST/Secret scans.
    """
    __tablename__ = "security_findings"

    finding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=False)
    severity = Column(String(50), nullable=False)
    remediation = Column(String, nullable=True)
    finding_type = Column(String(100), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="security_findings")


class DependencyScan(Base):
    """
    Vulnerabilities scanned in dependencies.
    """
    __tablename__ = "dependency_scans"

    scan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_name = Column(String(150), nullable=False)
    installed_version = Column(String(50), nullable=False)
    latest_version = Column(String(50), nullable=True)
    vulnerabilities_json = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="dependency_scans")


class SecretScan(Base):
    """
    Hardcoded password / API key scanner.
    """
    __tablename__ = "secret_scans"

    scan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(500), nullable=False)
    secret_type = Column(String(100), nullable=False)
    line_number = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="secret_scans")


class RbacAudit(Base):
    """
    Access controls configurations validation audit.
    """
    __tablename__ = "rbac_audits"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_name = Column(String(100), nullable=False)
    permissions_json = Column(JSON, nullable=True)
    audit_result = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="rbac_audits")


class SecurityReport(Base):
    """
    Detailed safety status security report metrics score.
    """
    __tablename__ = "security_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("security_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_name = Column(String(255), nullable=False)
    overall_risk_score = Column(Float, nullable=False)
    recommendations_json = Column(JSON, nullable=True)
    summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("SecurityGeneration", back_populates="security_reports")


# ── MILESTONE 12 – DevOps Agent Models ───────────────────────────────────────


class DevopsGeneration(Base):
    """
    Root record for a DevOps Agent generation run.
    """
    __tablename__ = "devops_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    frontend_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("frontend_generations.generation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("database_designs.design_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("architecture_reports.report_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="PENDING")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    docker_artifacts = relationship(
        "DockerArtifact", back_populates="generation", cascade="all, delete-orphan"
    )
    kubernetes_artifacts = relationship(
        "KubernetesArtifact", back_populates="generation", cascade="all, delete-orphan"
    )
    helm_artifacts = relationship(
        "HelmArtifact", back_populates="generation", cascade="all, delete-orphan"
    )
    terraform_artifacts = relationship(
        "TerraformArtifact", back_populates="generation", cascade="all, delete-orphan"
    )
    cicd_pipelines = relationship(
        "CicdPipeline", back_populates="generation", cascade="all, delete-orphan"
    )
    deployment_templates = relationship(
        "DeploymentTemplate", back_populates="generation", cascade="all, delete-orphan"
    )


class DockerArtifact(Base):
    """
    Dockerfile and docker-compose configurations.
    """
    __tablename__ = "docker_artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="docker_artifacts")


class KubernetesArtifact(Base):
    """
    Kubernetes manifests.
    """
    __tablename__ = "kubernetes_artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    manifest_name = Column(String(255), nullable=False)
    manifest_type = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="kubernetes_artifacts")


class HelmArtifact(Base):
    """
    Helm chart configuration files.
    """
    __tablename__ = "helm_artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(500), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="helm_artifacts")


class TerraformArtifact(Base):
    """
    Terraform infrastructure modules.
    """
    __tablename__ = "terraform_artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(500), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="terraform_artifacts")


class CicdPipeline(Base):
    """
    CI/CD pipeline scripts.
    """
    __tablename__ = "cicd_pipelines"

    pipeline_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="cicd_pipelines")


class DeploymentTemplate(Base):
    """
    Cloud platform configuration templates.
    """
    __tablename__ = "deployment_templates"

    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devops_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_platform = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("DevopsGeneration", back_populates="deployment_templates")


# ── MILESTONE 14 – Collaboration Engine Models ───────────────────────────────


class AgentCollaborationSession(Base):
    """
    Root record for a Multi-Agent Collaboration Session.
    """
    __tablename__ = "agent_collaboration_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    conversations = relationship(
        "AgentConversation", back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews = relationship(
        "AgentReview", back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )
    votes = relationship(
        "AgentVote", back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )
    conflicts = relationship(
        "AgentConflict", back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentConversation(Base):
    """
    Exchanged agent message threads / channels.
    """
    __tablename__ = "agent_conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_collaboration_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("AgentCollaborationSession", back_populates="conversations")
    messages = relationship(
        "AgentMessage", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentMessage(Base):
    """
    An individual message sent between agents.
    """
    __tablename__ = "agent_messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_agent = Column(String(100), nullable=False)
    recipient_agent = Column(String(100), nullable=True)
    content = Column(String, nullable=False)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    conversation = relationship("AgentConversation", back_populates="messages")


class AgentReview(Base):
    """
    Peer reviews and rework records.
    """
    __tablename__ = "agent_reviews"

    review_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_collaboration_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_agent = Column(String(100), nullable=False)
    target_agent = Column(String(100), nullable=False)
    artifact_type = Column(String(100), nullable=False)
    artifact_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(50), nullable=False)  # APPROVED, REWORK_REQUESTED
    comments = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("AgentCollaborationSession", back_populates="reviews")


class AgentVote(Base):
    """
    Consensus voting decision logs.
    """
    __tablename__ = "agent_votes"

    vote_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_collaboration_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic = Column(String(255), nullable=False)
    voter_agent = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False)  # YES, NO, ABSTAIN
    voted_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("AgentCollaborationSession", back_populates="votes")


class AgentConflict(Base):
    """
    Logged agent conflicts.
    """
    __tablename__ = "agent_conflicts"

    conflict_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_collaboration_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=False)
    severity = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(50), nullable=False, default="OPEN")  # OPEN, RESOLVED, ESCALATED
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("AgentCollaborationSession", back_populates="conflicts")
    resolutions = relationship(
        "AgentResolution", back_populates="conflict", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentResolution(Base):
    """
    Resolutions for logged conflicts.
    """
    __tablename__ = "agent_resolutions"

    resolution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conflict_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_conflicts.conflict_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolved_by = Column(String(100), nullable=False)  # e.g., "LeadAgent", "GovernanceEngine"
    resolution_strategy = Column(String(100), nullable=False)  # sequential review, vote, lead arbitration
    details = Column(String, nullable=False)
    resolved_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    conflict = relationship("AgentConflict", back_populates="resolutions")


# ─────────────────────────────────────────────────────────────────────────────
# MILESTONE 15 – Observability & Monitoring Platform
# ─────────────────────────────────────────────────────────────────────────────

class ObservabilityGeneration(Base):
    """
    Root record for a single observability snapshot run, linked to a workflow.
    """
    __tablename__ = "observability_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, COMPLETED, FAILED, SUPERSEDED
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Child relationships
    agent_metrics = relationship(
        "AgentMetric", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    workflow_metrics = relationship(
        "WorkflowMetric", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    api_metrics = relationship(
        "ApiMetric", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    system_metrics = relationship(
        "SystemMetric", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    error_events = relationship(
        "ErrorEvent", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    alert_rules = relationship(
        "AlertRule", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    alert_events = relationship(
        "AlertEvent", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentMetric(Base):
    """
    Per-agent performance counters captured during a generation run.
    """
    __tablename__ = "agent_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name = Column(String(100), nullable=False)
    duration_ms = Column(Float, nullable=False, default=0.0)
    tokens_used = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=1.0)   # 0.0 – 1.0
    error_count = Column(Integer, nullable=False, default=0)
    extra_metadata = Column(JSON, nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="agent_metrics")


class WorkflowMetric(Base):
    """
    Per-workflow step timing and throughput metrics.
    """
    __tablename__ = "workflow_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    step_name = Column(String(150), nullable=False)
    duration_ms = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="COMPLETED")  # COMPLETED, FAILED, SKIPPED
    throughput_rps = Column(Float, nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="workflow_metrics")


class ApiMetric(Base):
    """
    REST API endpoint latency and error-rate bucket snapshots.
    """
    __tablename__ = "api_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint = Column(String(300), nullable=False)
    method = Column(String(10), nullable=False, default="GET")
    avg_latency_ms = Column(Float, nullable=False, default=0.0)
    p99_latency_ms = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    request_count = Column(Integer, nullable=False, default=0)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="api_metrics")


class SystemMetric(Base):
    """
    Host-level CPU, memory, and disk utilisation snapshots.
    """
    __tablename__ = "system_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_name = Column(String(150), nullable=False)
    cpu_pct = Column(Float, nullable=False, default=0.0)
    memory_pct = Column(Float, nullable=False, default=0.0)
    disk_pct = Column(Float, nullable=False, default=0.0)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="system_metrics")


class ErrorEvent(Base):
    """
    Structured error log entries with severity and optional stack trace.
    """
    __tablename__ = "error_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(150), nullable=False)       # agent / endpoint / service name
    severity = Column(String(20), nullable=False, default="ERROR")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(String, nullable=False)
    stack_trace = Column(String, nullable=True)
    context = Column(JSON, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="error_events")


class AlertRule(Base):
    """
    Configurable threshold-based alert condition.
    """
    __tablename__ = "alert_rules"

    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_name = Column(String(200), nullable=False)
    metric_name = Column(String(150), nullable=False)
    operator = Column(String(10), nullable=False, default="gt")  # gt, lt, gte, lte, eq
    threshold = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, default="WARNING")  # INFO, WARNING, CRITICAL
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="alert_rules")
    alert_events = relationship(
        "AlertEvent", back_populates="rule", cascade="all, delete-orphan", lazy="selectin"
    )


class AlertEvent(Base):
    """
    A fired alert instance referencing the triggering rule.
    """
    __tablename__ = "alert_events"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.rule_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rule_name = Column(String(200), nullable=False)
    current_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, default="WARNING")
    message = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    fired_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("ObservabilityGeneration", back_populates="alert_events")
    rule = relationship("AlertRule", back_populates="alert_events")


# ─────────────────────────────────────────────────────────────────────────────
# MILESTONE 16 – Cost Optimization Agent
# ─────────────────────────────────────────────────────────────────────────────

class CostGeneration(Base):
    """
    Root record for a single cost-optimization analysis run, linked to a workflow.
    """
    __tablename__ = "cost_generations"

    generation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, COMPLETED, FAILED, SUPERSEDED
    total_cost = Column(Float, nullable=False, default=0.0)
    estimated_monthly_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Child relationships
    cost_reports = relationship(
        "CostReport", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    resource_usage_metrics = relationship(
        "ResourceUsageMetric", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    optimization_recommendations = relationship(
        "OptimizationRecommendation", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    savings_estimates = relationship(
        "SavingsEstimate", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )
    cost_alerts = relationship(
        "CostAlert", back_populates="generation", cascade="all, delete-orphan", lazy="selectin"
    )


class CostReport(Base):
    """
    Per-category cost breakdown for a generation run.
    """
    __tablename__ = "cost_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(String(100), nullable=False)  # LLM_TOKENS, API_REQUESTS, POSTGRESQL, QDRANT, REDIS, KAFKA, KUBERNETES
    current_cost = Column(Float, nullable=False, default=0.0)
    projected_cost = Column(Float, nullable=False, default=0.0)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("CostGeneration", back_populates="cost_reports")


class ResourceUsageMetric(Base):
    """
    Resource utilisation snapshot (CPU, memory, storage, tokens, API calls).
    """
    __tablename__ = "resource_usage_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = Column(String(100), nullable=False)  # CPU, MEMORY, STORAGE_GB, TOKENS, API_CALLS
    utilization_percent = Column(Float, nullable=False, default=0.0)
    consumption = Column(Float, nullable=False, default=0.0)
    unit = Column(String(50), nullable=False, default="%")  # %, GB, tokens, calls
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("CostGeneration", back_populates="resource_usage_metrics")


class OptimizationRecommendation(Base):
    """
    Actionable cost-optimization recommendation with impact level and savings estimate.
    """
    __tablename__ = "optimization_recommendations"

    recommendation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=False)
    impact_level = Column(String(20), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    estimated_savings = Column(Float, nullable=False, default=0.0)
    category = Column(String(100), nullable=True)  # e.g., LLM_TOKENS, KUBERNETES
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("CostGeneration", back_populates="optimization_recommendations")


class SavingsEstimate(Base):
    """
    Monthly and annual savings projections derived from optimization recommendations.
    """
    __tablename__ = "savings_estimates"

    estimate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monthly_savings = Column(Float, nullable=False, default=0.0)
    annual_savings = Column(Float, nullable=False, default=0.0)
    confidence_level = Column(String(20), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH
    assumptions = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("CostGeneration", back_populates="savings_estimates")


class BudgetPolicy(Base):
    """
    Project-level monthly budget threshold and alert configuration.
    Not generation-scoped — persists across multiple workflow runs.
    """
    __tablename__ = "budget_policies"

    policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    monthly_budget = Column(Float, nullable=False)
    alert_threshold = Column(Float, nullable=False, default=0.8)  # fraction of budget
    currency = Column(String(10), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    cost_alerts = relationship(
        "CostAlert", back_populates="policy", cascade="all, delete-orphan", lazy="selectin"
    )


class CostAlert(Base):
    """
    A fired cost threshold alert, optionally referencing a budget policy.
    """
    __tablename__ = "cost_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("budget_policies.policy_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    severity = Column(String(20), nullable=False, default="WARNING")  # INFO, WARNING, CRITICAL
    message = Column(String, nullable=False)
    current_cost = Column(Float, nullable=False, default=0.0)
    budget_limit = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    fired_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    generation = relationship("CostGeneration", back_populates="cost_alerts")
    policy = relationship("BudgetPolicy", back_populates="cost_alerts")


# ── MILESTONE 17 – Autonomous SDLC Controller ───────────────────────────────

class AutonomousController(Base):
    """
    Root execution run for the Autonomous SDLC Controller, linked to a workflow.
    """
    __tablename__ = "autonomous_controllers"

    controller_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="ACTIVE")  # ACTIVE, PAUSED, COMPLETED, FAILED
    current_step = Column(String(100), nullable=False)
    budget_limit = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    decisions = relationship("WorkflowDecision", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")
    retries = relationship("RetryHistory", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")
    failures = relationship("FailureEvent", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")
    rollbacks = relationship("RollbackEvent", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")
    execution_plans = relationship("ExecutionPlan", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")
    logs = relationship("ControllerLog", back_populates="controller", cascade="all, delete-orphan", lazy="selectin")


class WorkflowDecision(Base):
    """
    Key orchestration decisions taken by the controller.
    """
    __tablename__ = "workflow_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    step = Column(String(100), nullable=False)
    decision_type = Column(String(50), nullable=False)  # ROUTE, RETRY, ROLLBACK, APPROVE, COMPLETE, FAIL
    reason = Column(String, nullable=False)
    action_taken = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="decisions")


class AgentHealth(Base):
    """
    Heartbeat and health check registry for specialized SDLC agents.
    Not linked to a single controller run — persistent status tracker.
    """
    __tablename__ = "agent_health"

    health_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False, default="HEALTHY")  # HEALTHY, DEGRADED, UNHEALTHY
    last_heartbeat = Column(DateTime(timezone=True), default=datetime.utcnow)
    error_count = Column(Integer, nullable=False, default=0)
    avg_response_time = Column(Float, nullable=False, default=0.0)
    metadata_json = Column(JSON, nullable=True)


class RetryHistory(Base):
    """
    Automatic retry operations logs.
    """
    __tablename__ = "retry_history"

    retry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    step = Column(String(100), nullable=False)
    retry_attempt = Column(Integer, nullable=False, default=1)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(String, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="retries")


class FailureEvent(Base):
    """
    Collection of observed errors during step runs.
    """
    __tablename__ = "failure_events"

    failure_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    step = Column(String(100), nullable=False)
    error_type = Column(String(150), nullable=False)
    error_message = Column(String, nullable=False)
    severity = Column(String(50), nullable=False, default="ERROR")  # WARNING, ERROR, CRITICAL
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="failures")


class RollbackEvent(Base):
    """
    Rollback trigger registrations.
    """
    __tablename__ = "rollback_events"

    rollback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    source_step = Column(String(100), nullable=False)
    target_step = Column(String(100), nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="rollbacks")


class ExecutionPlan(Base):
    """
    Dynamic execution pipelines formulated by the controller.
    """
    __tablename__ = "execution_plans"

    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    steps_json = Column(JSON, nullable=False)
    current_step_index = Column(Integer, nullable=False, default=0)
    is_optimized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="execution_plans")


class ControllerLog(Base):
    """
    Controller run activity tracing log entries.
    """
    __tablename__ = "controller_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    controller_id = Column(UUID(as_uuid=True), ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    level = Column(String(20), nullable=False, default="INFO")  # INFO, WARNING, ERROR
    message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    controller = relationship("AutonomousController", back_populates="logs")



