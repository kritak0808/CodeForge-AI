import uuid
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import User, Project, Workflow, WorkflowState, ApprovalPolicy, ApprovalRequest, ApprovalResponse, ApprovalEscalation, ApprovalAuditLog
from app.services.approval import PolicyEvaluator, ApprovalRouter
from app.repositories.approval import ApprovalPolicyRepository, ApprovalRequestRepository, ApprovalResponseRepository, ApprovalEscalationRepository, ApprovalAuditLogRepository, ApprovalNotificationRepository
from app.repositories.workflow import WorkflowRepository, WorkflowStateRepository
from app.services.approval import ApprovalManager, ApprovalAuditService, EscalationManager
from event_publisher import KafkaEventPublisher

@pytest.mark.asyncio
async def test_policy_evaluation_rules(db_session: AsyncSession):
    """
    Verifies that policy evaluations dynamically trigger appropriate roles
    based on budget limits and action types.
    """
    policy_repo = ApprovalPolicyRepository(db_session)
    
    # Add dummy policies
    p1 = ApprovalPolicy(
        policy_id=uuid.uuid4(),
        name="Architecture Governance Rule",
        action_type="Architecture",
        required_role="Senior Engineer",
        min_approvers=1,
        timeout_hours=10
    )
    p2 = ApprovalPolicy(
        policy_id=uuid.uuid4(),
        name="Finance Budget Governance",
        action_type="Budget",
        required_role="Finance Manager",
        min_approvers=2,
        timeout_hours=24,
        budget_limit=50.00
    )
    await policy_repo.create(p1)
    await policy_repo.create(p2)

    policies = [p1, p2]
    
    # 1. Test Architecture match
    match1 = PolicyEvaluator.evaluate("Architecture", {}, policies)
    assert match1 is not None
    assert match1.required_role == "Senior Engineer"

    # 2. Test Budget match under threshold
    match2 = PolicyEvaluator.evaluate("Budget", {"budget": 10.00}, policies)
    assert match2 is not None
    assert match2.required_role == "Finance Manager" # fallback matches because action_type matches

    # 3. Test Budget match above threshold
    match3 = PolicyEvaluator.evaluate("Budget", {"budget": 150.00}, policies)
    assert match3 is not None
    assert match3.required_role == "Finance Manager"

@pytest.mark.asyncio
async def test_approval_governance_api_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Executes a complete REST workflow for request submission, approvals,
    rejections, rework flags, and audit trace assertions.
    """
    # 1. Register and Login Reviewer
    reg_payload = {
        "username": "govreviewer",
        "email": "govreviewer@codeforge.ai",
        "password": "securepassword123",
        "role": "Senior Engineer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    login_payload = {
        "username": "govreviewer",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Extract user ID
    user_query = select(User).filter(User.username == "govreviewer")
    res_user = await db_session.execute(user_query)
    user_obj = res_user.scalars().first()
    user_id = user_obj.user_id

    # 2. Setup Project & Workflow
    project = Project(user_id=user_id, name="GovProj", tech_stack={})
    db_session.add(project)
    await db_session.commit()

    workflow = Workflow(workflow_id=uuid.uuid4(), project_id=project.project_id, current_state="PLANNING")
    db_session.add(workflow)
    
    state_entry = WorkflowState(workflow_id=workflow.workflow_id, state="PLANNING")
    db_session.add(state_entry)
    await db_session.commit()

    # 3. Create mock Approval Policy in DB
    policy = ApprovalPolicy(
        policy_id=uuid.uuid4(),
        name="Architecture Policy",
        action_type="Architecture",
        required_role="Senior Engineer",
        min_approvers=1,
        timeout_hours=12
    )
    db_session.add(policy)
    await db_session.commit()

    # 4. Trigger REST approval request
    req_payload = {
        "workflow_id": str(workflow.workflow_id),
        "approval_type": "Architecture",
        "context": {"budget": 20.00}
    }
    req_resp = await client.post("/api/v1/approvals/request", json=req_payload, headers=headers)
    assert req_resp.status_code == 201
    approval_id = req_resp.json()["data"]["approval_id"]

    # Verify state transitioned to WAITING_FOR_APPROVAL
    await db_session.refresh(workflow)
    assert workflow.current_state == "WAITING_FOR_APPROVAL"

    # 5. List approvals
    list_resp = await client.get("/api/v1/approvals/pending", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) > 0

    # 6. Submit approve decision
    decision_payload = {
        "comments": "Architectural design approved successfully",
        "signature": "SHA256:govreviewer:signature:hash"
    }
    approve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json=decision_payload,
        headers=headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["decision"] == "APPROVED"

    # Check request status changed in database
    req_query = select(ApprovalRequest).filter(ApprovalRequest.approval_id == uuid.UUID(approval_id))
    res_req = await db_session.execute(req_query)
    req_obj = res_req.scalars().first()
    assert req_obj.status == "APPROVED"

    # Verify workflow resumed and transitioned to next state (DATABASE_DESIGN)
    await db_session.refresh(workflow)
    assert workflow.current_state == "DATABASE_DESIGN"

    # 7. Verify Audit trail has been logged
    audit_query = select(ApprovalAuditLog).filter(ApprovalAuditLog.workflow_id == workflow.workflow_id)
    res_audit = await db_session.execute(audit_query)
    audit_obj = res_audit.scalars().first()
    assert audit_obj is not None
    assert audit_obj.decision == "APPROVED"
    assert audit_obj.signature == "SHA256:govreviewer:signature:hash"

@pytest.mark.asyncio
async def test_escalation_manager_timeouts(db_session: AsyncSession):
    """
    Verifies that the EscalationManager detects timeouts and schedules forwards.
    """
    # Create base records
    user = User(username="escuser", email="esc@codeforge.ai", password_hash="pass", role="developer")
    db_session.add(user)
    await db_session.commit()

    project = Project(user_id=user.user_id, name="EscProj", tech_stack={})
    db_session.add(project)
    await db_session.commit()

    workflow = Workflow(workflow_id=uuid.uuid4(), project_id=project.project_id, current_state="WAITING_FOR_APPROVAL")
    db_session.add(workflow)
    await db_session.commit()

    # Create request
    req = ApprovalRequest(
        approval_id=uuid.uuid4(),
        workflow_id=workflow.workflow_id,
        approval_type="Deployment",
        status="WAITING_FOR_APPROVAL"
    )
    db_session.add(req)
    await db_session.commit()

    # Create expired escalation
    escalation = ApprovalEscalation(
        escalation_id=uuid.uuid4(),
        approval_id=req.approval_id,
        escalation_role="Admin",
        status="PENDING",
        scheduled_at=datetime.utcnow() - timedelta(hours=1)  # Expired
    )
    db_session.add(escalation)
    await db_session.commit()

    # Overwrite sync session maker for EscalationManager
    req_repo = ApprovalRequestRepository(db_session)
    esc_repo = ApprovalEscalationRepository(db_session)
    state_repo = WorkflowStateRepository(db_session)
    wf_repo = WorkflowRepository(db_session)
    audit_repo = ApprovalAuditLogRepository(db_session)
    audit_service = ApprovalAuditService(audit_repo)
    event_pub = KafkaEventPublisher(bootstrap_servers="localhost:9999")

    manager = EscalationManager(
        request_repo=req_repo,
        escalation_repo=esc_repo,
        state_repo=state_repo,
        workflow_repo=wf_repo,
        audit_service=audit_service,
        event_pub=event_pub
    )

    # Perform scan
    count = await manager.scan_and_escalate()
    assert count == 1

    # Verify request status transitioned to ESCALATED
    await db_session.refresh(req)
    assert req.status == "ESCALATED"

    # Verify escalation status changed to ESCALATED
    await db_session.refresh(escalation)
    assert escalation.status == "ESCALATED"
