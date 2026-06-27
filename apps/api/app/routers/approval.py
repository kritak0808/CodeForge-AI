import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.token import TokenData
from app.schemas.approval import (
    ApprovalPolicyCreate, ApprovalPolicyResponse,
    ApprovalRequestCreate, ApprovalRequestResponse, ApprovalRequestDetails,
    ApprovalResponseCreate, ApprovalResponseDetails
)
from app.models import ApprovalPolicy, ApprovalRequest, ApprovalResponse, ApprovalEscalation, ApprovalNotification, ApprovalAuditLog, Workflow, WorkflowState
from app.repositories.approval import (
    ApprovalPolicyRepository,
    ApprovalRequestRepository,
    ApprovalResponseRepository,
    ApprovalEscalationRepository,
    ApprovalNotificationRepository,
    ApprovalAuditLogRepository
)
from app.repositories.workflow import WorkflowRepository, WorkflowStateRepository
from app.services.approval import ApprovalManager, ApprovalAuditService, EscalationManager

# Create router (prefix="/approvals", tags=["Approvals"])
router = APIRouter(prefix="/approvals", tags=["Approvals"])

# Inline dependency injection helpers
def get_approval_manager(db: AsyncSession = Depends(get_db)) -> ApprovalManager:
    policy_repo = ApprovalPolicyRepository(db)
    request_repo = ApprovalRequestRepository(db)
    response_repo = ApprovalResponseRepository(db)
    escalation_repo = ApprovalEscalationRepository(db)
    notification_repo = ApprovalNotificationRepository(db)
    audit_repo = ApprovalAuditLogRepository(db)
    audit_service = ApprovalAuditService(audit_repo)
    workflow_repo = WorkflowRepository(db)
    state_repo = WorkflowStateRepository(db)
    
    return ApprovalManager(
        policy_repo=policy_repo,
        request_repo=request_repo,
        response_repo=response_repo,
        escalation_repo=escalation_repo,
        notification_repo=notification_repo,
        audit_service=audit_service,
        workflow_repo=workflow_repo,
        state_repo=state_repo
    )

from pydantic import BaseModel
class RequestPayload(BaseModel):
    workflow_id: uuid.UUID
    approval_type: str
    context: Dict[str, Any] = {}

class ReworkPayload(BaseModel):
    comments: Optional[str] = None
    signature: Optional[str] = "system"   # frontend doesn't send this; default to "system"

class DecisionPayload(BaseModel):
    comments: Optional[str] = None
    notes: Optional[str] = None           # frontend sends "notes", map to comments
    signature: Optional[str] = "system"  # frontend doesn't send this; default to "system"

    @property
    def resolved_comments(self) -> Optional[str]:
        return self.comments or self.notes

    @property
    def resolved_signature(self) -> str:
        return self.signature or "system"

# --- Endpoints ---

@router.post("/request", response_model=dict, status_code=status.HTTP_201_CREATED)
async def request_approval(
    payload: RequestPayload,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Creates a pending human validation request for a critical workflow action.
    """
    req = await manager.request_approval(payload.workflow_id, payload.approval_type, payload.context)
    return {
        "success": True,
        "data": {
            "approval_id": str(req.approval_id),
            "workflow_id": str(req.workflow_id),
            "approval_type": req.approval_type,
            "status": req.status,
            "created_at": req.created_at.isoformat()
        },
        "error": None
    }

@router.post("/{approval_id}/approve", response_model=dict)
async def approve_request(
    approval_id: uuid.UUID,
    payload: DecisionPayload,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Approves the pending human validation request.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    resp = await manager.submit_response(
        approval_id=approval_id,
        user_id=user_id,
        decision="APPROVED",
        comments=payload.resolved_comments,
        signature=payload.resolved_signature
    )
    return {
        "success": True,
        "data": {
            "response_id": str(resp.response_id),
            "approval_id": str(resp.approval_id),
            "decision": resp.decision,
            "signature": resp.signature,
            "created_at": resp.created_at.isoformat()
        },
        "error": None
    }

@router.post("/{approval_id}/reject", response_model=dict)
async def reject_request(
    approval_id: uuid.UUID,
    payload: DecisionPayload,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Rejects the pending human validation request.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    resp = await manager.submit_response(
        approval_id=approval_id,
        user_id=user_id,
        decision="REJECTED",
        comments=payload.resolved_comments,
        signature=payload.resolved_signature
    )
    return {
        "success": True,
        "data": {
            "response_id": str(resp.response_id),
            "approval_id": str(resp.approval_id),
            "decision": resp.decision,
            "signature": resp.signature,
            "created_at": resp.created_at.isoformat()
        },
        "error": None
    }

@router.post("/{approval_id}/rework", response_model=dict)
async def rework_request(
    approval_id: uuid.UUID,
    payload: ReworkPayload,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Requests rework on the pending human validation request.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    resp = await manager.submit_response(
        approval_id=approval_id,
        user_id=user_id,
        decision="REWORK",
        comments=payload.comments,
        signature=payload.signature or "system"
    )
    return {
        "success": True,
        "data": {
            "response_id": str(resp.response_id),
            "approval_id": str(resp.approval_id),
            "decision": resp.decision,
            "signature": resp.signature,
            "created_at": resp.created_at.isoformat()
        },
        "error": None
    }

@router.get("/", response_model=dict)
async def list_approvals(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Lists all approval requests, optionally filtered by status.
    Accepts ?status=pending|approved|rejected etc.
    """
    if status and status.lower() in ("pending", "waiting"):
        requests = await manager.request_repo.get_pending_requests()
    else:
        requests = await manager.request_repo.list()

    # Normalise status values to lowercase for the frontend
    _status_map = {
        "WAITING_FOR_APPROVAL": "pending",
        "APPROVED": "approved",
        "REJECTED": "rejected",
        "REWORK_REQUIRED": "pending",
        "EXPIRED": "rejected",
        "ESCALATED": "pending",
    }

    return {
        "success": True,
        "data": [
            {
                "approval_id":   str(r.approval_id),
                "workflow_id":   str(r.workflow_id),
                "approval_type": r.approval_type,
                "status":        _status_map.get(r.status, r.status.lower()),
                "requested_at":  r.created_at.isoformat(),
                "decided_at":    r.updated_at.isoformat() if r.status not in ("WAITING_FOR_APPROVAL", "ESCALATED", "REWORK_REQUIRED") else None,
                "notes":         None,
            }
            for r in requests
        ],
        "error": None,
    }

@router.get("/pending", response_model=dict)
async def list_pending_approvals(
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Lists only pending approval requests in the system.
    """
    requests = await manager.request_repo.get_pending_requests()
    return {
        "success": True,
        "data": [
            {
                "approval_id":   str(r.approval_id),
                "workflow_id":   str(r.workflow_id),
                "approval_type": r.approval_type,
                "status":        "pending",
                "requested_at":  r.created_at.isoformat(),
                "decided_at":    None,
                "notes":         None,
            }
            for r in requests
        ],
        "error": None,
    }

@router.get("/{approval_id}", response_model=dict)
async def get_approval_details(
    approval_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    manager: ApprovalManager = Depends(get_approval_manager)
):
    """
    Gets detailed metadata of a specific approval request.
    """
    req = await manager.request_repo.get_request_details(approval_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )
    return {
        "success": True,
        "data": {
            "approval_id": str(req.approval_id),
            "workflow_id": str(req.workflow_id),
            "approval_type": req.approval_type,
            "status": req.status,
            "created_at": req.created_at.isoformat(),
            "updated_at": req.updated_at.isoformat(),
            "policy": {
                "policy_id": str(req.policy.policy_id),
                "name": req.policy.name,
                "action_type": req.policy.action_type,
                "required_role": req.policy.required_role
            } if req.policy else None,
            "responses": [
                {
                    "response_id": str(resp.response_id),
                    "user_id": str(resp.user_id),
                    "decision": resp.decision,
                    "comments": resp.comments,
                    "signature": resp.signature,
                    "created_at": resp.created_at.isoformat()
                }
                for resp in req.responses
            ],
            "escalations": [
                {
                    "escalation_id": str(e.escalation_id),
                    "escalation_role": e.escalation_role,
                    "status": e.status,
                    "scheduled_at": e.scheduled_at.isoformat(),
                    "escalated_at": e.escalated_at.isoformat() if e.escalated_at else None
                }
                for e in req.escalations
            ],
            "notifications": [
                {
                    "notification_id": str(n.notification_id),
                    "channel": n.channel,
                    "status": n.status,
                    "message": n.message,
                    "sent_at": n.sent_at.isoformat()
                }
                for n in req.notifications
            ]
        },
        "error": None
    }
