import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select

from app.models import ApprovalPolicy, ApprovalRequest, ApprovalResponse, ApprovalEscalation, ApprovalNotification, ApprovalAuditLog, Workflow, WorkflowState, Approval
from app.repositories.approval import (
    ApprovalPolicyRepository,
    ApprovalRequestRepository,
    ApprovalResponseRepository,
    ApprovalEscalationRepository,
    ApprovalNotificationRepository,
    ApprovalAuditLogRepository
)
from app.repositories.workflow import WorkflowRepository, WorkflowStateRepository

import sys
import os

# Lazy Kafka import — avoids blocking connection attempt at import time
orchestrator_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent-orchestrator")
)
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

try:
    from event_publisher import KafkaEventPublisher as _KafkaEventPublisher
    _kafka_available = True
except ImportError:
    _KafkaEventPublisher = None  # type: ignore[assignment,misc]
    _kafka_available = False

logger = logging.getLogger("api-gateway.approval-service")

class PolicyEvaluator:
    @staticmethod
    def evaluate(action_type: str, context: Dict[str, Any], policies: List[ApprovalPolicy]) -> Optional[ApprovalPolicy]:
        """
        Evaluates policies to match the best rule.
        Rules:
        - If context has a budget/cost and budget exceeds policy budget_limit, return that policy.
        - Match required action_type.
        """
        matched_policy = None
        for policy in policies:
            if policy.action_type.lower() != action_type.lower():
                continue
            
            # Budget rule check
            if policy.budget_limit is not None and "budget" in context:
                if float(context["budget"]) >= float(policy.budget_limit):
                    return policy
            
            matched_policy = policy
            
        return matched_policy

class ApprovalRouter:
    @staticmethod
    def route_request(request: ApprovalRequest, policy: Optional[ApprovalPolicy]) -> str:
        """
        Determines the target reviewer role.
        """
        if policy:
            return policy.required_role
        
        # Default routing fallbacks
        mapping = {
            "Architecture": "Senior Engineer",
            "Database": "Senior Engineer",
            "Technology": "Senior Engineer",
            "Security": "Security",
            "Deployment": "Admin",
            "Budget": "Finance",
            "Emergency": "Admin"
        }
        return mapping.get(request.approval_type, "Senior Engineer")

class ApprovalAuditService:
    def __init__(self, audit_repo: ApprovalAuditLogRepository):
        self.audit_repo = audit_repo

    async def log_audit(
        self,
        workflow_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
        agent_id: Optional[str],
        reason: Optional[str],
        decision: str,
        signature: Optional[str]
    ) -> ApprovalAuditLog:
        audit = ApprovalAuditLog(
            audit_id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            reason=reason,
            decision=decision,
            signature=signature
        )
        await self.audit_repo.create(audit)
        return audit

class ApprovalManager:
    def __init__(
        self,
        policy_repo: ApprovalPolicyRepository,
        request_repo: ApprovalRequestRepository,
        response_repo: ApprovalResponseRepository,
        escalation_repo: ApprovalEscalationRepository,
        notification_repo: ApprovalNotificationRepository,
        audit_service: ApprovalAuditService,
        workflow_repo: WorkflowRepository,
        state_repo: WorkflowStateRepository,
        event_pub=None,
    ):
        self.policy_repo = policy_repo
        self.request_repo = request_repo
        self.response_repo = response_repo
        self.escalation_repo = escalation_repo
        self.notification_repo = notification_repo
        self.audit_service = audit_service
        self.workflow_repo = workflow_repo
        self.state_repo = state_repo

        # Kafka publisher — only instantiate when Kafka is enabled in config
        if event_pub is not None:
            self.event_pub = event_pub
        elif _kafka_available and _KafkaEventPublisher is not None:
            try:
                self.event_pub = _KafkaEventPublisher()
            except Exception as exc:
                logger.debug(f"Kafka publisher unavailable (approval service): {exc}")
                self.event_pub = None
        else:
            self.event_pub = None

    async def request_approval(
        self,
        workflow_id: uuid.UUID,
        approval_type: str,
        context: Dict[str, Any]
    ) -> ApprovalRequest:
        """
        Creates a new pending human approval request, evaluates routing policies, 
        schedules escalations, publishes events, and notifies channels.
        """
        # Load all policies to evaluate
        policies = await self.policy_repo.list()
        matched_policy = PolicyEvaluator.evaluate(approval_type, context, policies)
        
        policy_id = matched_policy.policy_id if matched_policy else None
        timeout_hours = matched_policy.timeout_hours if matched_policy else 24

        # 1. Save request record
        req = ApprovalRequest(
            approval_id=uuid.uuid4(),
            workflow_id=workflow_id,
            approval_type=approval_type,
            status="WAITING_FOR_APPROVAL",
            policy_id=policy_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await self.request_repo.create(req)

        # 2. Update master workflow state to WAITING_FOR_APPROVAL
        workflow = await self.workflow_repo.get(workflow_id)
        if workflow:
            # Exits current state
            active_state = await self.state_repo.get_active_state(workflow_id)
            if active_state:
                active_state.exited_at = datetime.utcnow()
                await self.state_repo.update(active_state, active_state)

            waiting_state = WorkflowState(
                workflow_id=workflow_id,
                state="WAITING_FOR_APPROVAL",
                entered_at=datetime.utcnow(),
                metadata_json={"approval_id": str(req.approval_id), "type": approval_type}
            )
            await self.state_repo.create(waiting_state)

            workflow.current_state = "WAITING_FOR_APPROVAL"
            workflow.updated_at = datetime.utcnow()
            await self.workflow_repo.update(workflow, workflow)

        # 3. Schedule escalation
        target_role = ApprovalRouter.route_request(req, matched_policy)
        escalation = ApprovalEscalation(
            escalation_id=uuid.uuid4(),
            approval_id=req.approval_id,
            escalation_role="Admin",  # Escalate to administrator by default
            status="PENDING",
            scheduled_at=datetime.utcnow() + timedelta(hours=timeout_hours)
        )
        await self.escalation_repo.create(escalation)

        # 4. Trigger channel notifications
        channels = ["Email", "Slack", "SSE", "Dashboard"]
        message = f"Approval Required: {approval_type} validation for workflow {workflow_id}. Assignee: {target_role}."
        for chan in channels:
            notif = ApprovalNotification(
                notification_id=uuid.uuid4(),
                approval_id=req.approval_id,
                channel=chan,
                status="SENT",
                message=message,
                sent_at=datetime.utcnow()
            )
            await self.notification_repo.create(notif)
            logger.info(f"[Notification Alert] Channel: {chan} | Message: {message}")

        # 5. Publish Kafka Event
        if self.event_pub:
            self.event_pub.publish("approval.events", {
                "event_type": "approval.requested",
                "approval_id": str(req.approval_id),
                "workflow_id": str(workflow_id),
                "approval_type": approval_type,
                "target_role": target_role,
                "timestamp": datetime.utcnow().isoformat()
            })

        return req

    async def submit_response(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
        decision: str,  # APPROVED, REJECTED, REWORK
        comments: Optional[str],
        signature: str
    ) -> ApprovalResponse:
        """
        Saves user response signature, updates approval request status, resumes/rejects workflow engine,
        records immutable audit trail, and fires Kafka notices.
        """
        req = await self.request_repo.get(approval_id)
        if not req:
            from app.exceptions import NotFoundException
            raise NotFoundException("Approval request not found")

        if req.status != "WAITING_FOR_APPROVAL":
            from app.exceptions import ConflictException
            raise ConflictException("This approval request has already been resolved")

        # 1. Record response details
        resp = ApprovalResponse(
            response_id=uuid.uuid4(),
            approval_id=approval_id,
            user_id=user_id,
            decision=decision,
            comments=comments,
            signature=signature,
            created_at=datetime.utcnow()
        )
        await self.response_repo.create(resp)

        # 2. Update request status matching decision mapping
        status_map = {
            "APPROVED": "APPROVED",
            "REJECTED": "REJECTED",
            "REWORK": "REWORK_REQUIRED"
        }
        req.status = status_map.get(decision, "REJECTED")
        req.updated_at = datetime.utcnow()
        await self.request_repo.update(req, req)

        # Mark escalation as RESOLVED since request is processed
        query_esc = (
            select(ApprovalEscalation)
            .filter(ApprovalEscalation.approval_id == approval_id, ApprovalEscalation.status == "PENDING")
        )
        res_esc = await self.escalation_repo.db.execute(query_esc)
        esc = res_esc.scalars().first()
        if esc:
            esc.status = "RESOLVED"
            await self.escalation_repo.update(esc, esc)

        # 3. Route & Resume Workflow Engine state machine
        workflow = await self.workflow_repo.get(req.workflow_id)
        if workflow:
            # Exits WAITING_FOR_APPROVAL state
            active_state = await self.state_repo.get_active_state(req.workflow_id)
            if active_state:
                active_state.exited_at = datetime.utcnow()
                await self.state_repo.update(active_state, active_state)

            # Route to next state
            next_state = "FAILED"
            if decision == "APPROVED":
                # Progressive node routing based on approval type
                if req.approval_type == "Architecture":
                    next_state = "DATABASE_DESIGN"
                elif req.approval_type == "Security":
                    next_state = "DEPLOYING"
                elif req.approval_type == "Deployment":
                    next_state = "COMPLETED"
                else:
                    next_state = "COMPLETED"
            elif decision == "REWORK":
                # Rollback starting loop
                next_state = "PLANNING"
            else:
                # Terminate workflow
                next_state = "FAILED"

            new_state_entry = WorkflowState(
                workflow_id=workflow.workflow_id,
                state=next_state,
                entered_at=datetime.utcnow()
            )
            await self.state_repo.create(new_state_entry)

            workflow.current_state = next_state
            workflow.updated_at = datetime.utcnow()
            await self.workflow_repo.update(workflow, workflow)

            # Trigger resume check in background orchestrator if approved
            if decision == "APPROVED" and self.event_pub:
                self.event_pub.publish("workflow.events", {
                    "event_type": "TRIGGER_STATE_STEP",
                    "workflow_id": str(workflow.workflow_id)
                })

        # Update sync Approval table if exists
        try:
            from app.models import Approval
            from sqlalchemy import update
            stmt = update(Approval).where(Approval.approval_id == approval_id).values(
                status="APPROVED" if decision == "APPROVED" else "REJECTED",
                comments=comments,
                decided_at=datetime.utcnow()
            )
            await self.request_repo.db.execute(stmt)
            await self.request_repo.db.commit()
        except Exception as e:
            logger.warning(f"Failed to update sync Approval table: {e}")

        # 4. Generate immutable audit logs entry
        await self.audit_service.log_audit(
            workflow_id=req.workflow_id,
            actor_id=user_id,
            agent_id=None,
            reason=comments or "Decision recorded",
            decision=decision,
            signature=signature
        )

        # 5. Publish Kafka Event
        topic_map = {
            "APPROVED": "approval.approved",
            "REJECTED": "approval.rejected",
            "REWORK": "approval.rework"
        }
        if self.event_pub:
            self.event_pub.publish("approval.events", {
                "event_type": topic_map.get(decision, "approval.rejected"),
                "approval_id": str(approval_id),
                "workflow_id": str(req.workflow_id),
                "user_id": str(user_id),
                "comments": comments,
                "signature": signature,
                "timestamp": datetime.utcnow().isoformat()
            })

        return resp

class EscalationManager:
    def __init__(
        self,
        request_repo: ApprovalRequestRepository,
        escalation_repo: ApprovalEscalationRepository,
        state_repo: WorkflowStateRepository,
        workflow_repo: WorkflowRepository,
        audit_service: ApprovalAuditService,
        event_pub=None,   # Optional; KafkaEventPublisher or None
    ):
        self.request_repo = request_repo
        self.escalation_repo = escalation_repo
        self.state_repo = state_repo
        self.workflow_repo = workflow_repo
        self.audit_service = audit_service
        self.event_pub = event_pub

    async def scan_and_escalate(self) -> int:
        """
        Finds pending escalations where scheduled time has expired, transitions requests to ESCALATED or EXPIRED,
        notifies admins, audits the action, and publishes alerts.
        """
        untriggered = await self.escalation_repo.get_untriggered_escalations()
        escalated_count = 0
        
        for esc in untriggered:
            req = await self.request_repo.get(esc.approval_id)
            if not req or req.status != "WAITING_FOR_APPROVAL":
                esc.status = "RESOLVED"
                await self.escalation_repo.update(esc, esc)
                continue

            # Update request to ESCALATED
            req.status = "ESCALATED"
            req.updated_at = datetime.utcnow()
            await self.request_repo.update(req, req)

            esc.status = "ESCALATED"
            esc.escalated_at = datetime.utcnow()
            await self.escalation_repo.update(esc, esc)

            # Log audit
            await self.audit_service.log_audit(
                workflow_id=req.workflow_id,
                actor_id=None,
                agent_id="EscalationManager",
                reason="Escalated due to response timeout limit reached.",
                decision="ESCALATED",
                signature="SYSTEM_AUTO_ESCALATION"
            )

            # Publish Kafka Event
            if self.event_pub:
                self.event_pub.publish("approval.events", {
                    "event_type": "approval.escalated",
                    "approval_id": str(req.approval_id),
                    "workflow_id": str(req.workflow_id),
                    "escalated_to": esc.escalation_role,
                    "timestamp": datetime.utcnow().isoformat()
                })

            escalated_count += 1
            logger.warning(f"Timeout reached. Escalated approval request {req.approval_id} for workflow {req.workflow_id} to Admin.")

        return escalated_count
