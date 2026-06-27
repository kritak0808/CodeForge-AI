from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# --- Policy Schemas ---
class ApprovalPolicyBase(BaseModel):
    name: str
    action_type: str
    required_role: str
    min_approvers: int = 1
    timeout_hours: int = 24
    budget_limit: Optional[float] = None

class ApprovalPolicyCreate(ApprovalPolicyBase):
    pass

class ApprovalPolicyResponse(ApprovalPolicyBase):
    policy_id: UUID

    model_config = ConfigDict(from_attributes=True)


# --- Request Schemas ---
class ApprovalRequestBase(BaseModel):
    workflow_id: UUID
    approval_type: str
    policy_id: Optional[UUID] = None

class ApprovalRequestCreate(ApprovalRequestBase):
    pass

class ApprovalRequestResponse(BaseModel):
    approval_id: UUID
    workflow_id: UUID
    approval_type: str
    status: str
    policy_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Response Schemas ---
class ApprovalResponseBase(BaseModel):
    approval_id: UUID
    decision: str  # APPROVED, REJECTED, REWORK
    comments: Optional[str] = None
    signature: str

class ApprovalResponseCreate(ApprovalResponseBase):
    pass

class ApprovalResponseDetails(ApprovalResponseBase):
    response_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Escalation, Notification, Audit Schemas ---
class ApprovalEscalationResponse(BaseModel):
    escalation_id: UUID
    approval_id: UUID
    escalation_role: str
    status: str
    scheduled_at: datetime
    escalated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ApprovalNotificationResponse(BaseModel):
    notification_id: UUID
    approval_id: UUID
    channel: str
    status: str
    message: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ApprovalAuditLogResponse(BaseModel):
    audit_id: UUID
    timestamp: datetime
    actor_id: Optional[UUID] = None
    workflow_id: UUID
    agent_id: Optional[str] = None
    reason: Optional[str] = None
    decision: str
    signature: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Aggregated Request Status Schema ---
class ApprovalRequestDetails(ApprovalRequestResponse):
    policy: Optional[ApprovalPolicyResponse] = None
    responses: List[ApprovalResponseDetails] = []
    escalations: List[ApprovalEscalationResponse] = []
    notifications: List[ApprovalNotificationResponse] = []

    model_config = ConfigDict(from_attributes=True)
