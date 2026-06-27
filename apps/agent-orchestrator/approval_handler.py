import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Approval, Workflow, WorkflowState, ApprovalRequest, ApprovalEscalation, ApprovalNotification
from event_publisher import KafkaEventPublisher

logger = logging.getLogger("agent-orchestrator.approval-handler")

_STATE_TO_STATUS = {
    "CREATED":               "CREATED",
    "PLANNING":              "RUNNING",
    "RESEARCHING":           "RUNNING",
    "ARCHITECTING":          "RUNNING",
    "DATABASE_DESIGN":       "RUNNING",
    "BACKEND_GENERATION":    "RUNNING",
    "FRONTEND_GENERATION":   "RUNNING",
    "TESTING":               "RUNNING",
    "SECURITY_REVIEW":       "RUNNING",
    "DEVOPS_GENERATION":     "RUNNING",
    "APPROVAL_PENDING":      "PAUSED",
    "DEPLOYING":             "RUNNING",
    "OBSERVABILITY":         "RUNNING",
    "COST_OPTIMIZATION":     "RUNNING",
    "AUTONOMOUS_CONTROLLER": "RUNNING",
    "FINAL_DEPLOYMENT":      "RUNNING",
    "COMPLETED":             "COMPLETED",
    "FAILED":                "FAILED",
    "CANCELLED":             "CANCELLED",
    "PAUSED":                "PAUSED",
    "INITIATED":             "CREATED",
}

class ApprovalHandler:
    def __init__(self, db_url: str, event_pub: KafkaEventPublisher, timeout_hours: int = 24):
        # Convert async driver dialects if present for sync sqlalchemy engine
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.event_pub = event_pub
        self.timeout_hours = timeout_hours

    def request_approval(self, workflow_id: str, approval_type: str, artifact_payload: Dict[str, Any]) -> str:
        """
        Creates a pending approval request and fires a Kafka notice.
        """
        session = self.SessionLocal()
        try:
            approval_id = uuid.uuid4()
            approval = Approval(
                approval_id=approval_id,
                workflow_id=uuid.UUID(workflow_id),
                approval_type=approval_type,
                status="PENDING",
                artifact_payload=artifact_payload,
                created_at=datetime.utcnow()
            )
            session.add(approval)

            # Insert into approval_requests to align with API Gateway
            approval_req = ApprovalRequest(
                approval_id=approval_id,
                workflow_id=uuid.UUID(workflow_id),
                approval_type=approval_type,
                status="WAITING_FOR_APPROVAL",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(approval_req)

            # Insert a default escalation schedule
            escalation = ApprovalEscalation(
                escalation_id=uuid.uuid4(),
                approval_id=approval_id,
                escalation_role="Admin",
                status="PENDING",
                scheduled_at=datetime.utcnow() + timedelta(hours=self.timeout_hours)
            )
            session.add(escalation)

            # Insert a default notification log
            notif = ApprovalNotification(
                notification_id=uuid.uuid4(),
                approval_id=approval_id,
                channel="Dashboard",
                status="SENT",
                message=f"Approval Required: {approval_type} validation for workflow {workflow_id}.",
                sent_at=datetime.utcnow()
            )
            session.add(notif)

            # Insert WORKFLOWState change to APPROVAL_PENDING
            session.query(WorkflowState).filter(
                WorkflowState.workflow_id == uuid.UUID(workflow_id),
                WorkflowState.exited_at == None
            ).update({
                WorkflowState.exited_at: datetime.utcnow()
            }, synchronize_session=False)

            pending_state = WorkflowState(
                workflow_id=uuid.UUID(workflow_id),
                state="APPROVAL_PENDING",
                entered_at=datetime.utcnow(),
                metadata_json={"approval_id": str(approval_id), "type": approval_type}
            )
            session.add(pending_state)

            # Update master workflow state
            session.query(Workflow).filter(
                Workflow.workflow_id == uuid.UUID(workflow_id)
            ).update({
                Workflow.current_state: "APPROVAL_PENDING",
                Workflow.status: "PAUSED",
                Workflow.updated_at: datetime.utcnow()
            }, synchronize_session=False)

            session.commit()

            # Publish event
            self.event_pub.publish("approval.events", {
                "event_type": "APPROVAL_REQUESTED",
                "approval_id": str(approval_id),
                "workflow_id": workflow_id,
                "approval_type": approval_type,
                "created_at": approval.created_at.isoformat()
            })

            logger.info(f"Created pending approval '{approval_type}' ({approval_id}) for workflow {workflow_id}")
            return str(approval_id)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create approval request: {e}")
            raise
        finally:
            session.close()

    def process_decision(self, approval_id: str, status: str, comments: Optional[str], user_id: str) -> Dict[str, Any]:
        """
        Updates database records for approvals and triggers recovery steps.
        Status must be: APPROVED or REJECTED.
        """
        session = self.SessionLocal()
        try:
            approval = session.query(Approval).filter(Approval.approval_id == uuid.UUID(approval_id)).first()
            if not approval:
                return {"success": False, "message": "Approval request not found"}

            if approval.status != "PENDING":
                return {"success": False, "message": "Approval request is already processed"}

            # Update record
            approval.status = status
            approval.comments = comments
            approval.approver_id = uuid.UUID(user_id) if user_id and user_id != str(uuid.UUID(int=0)) else None
            approval.decided_at = datetime.utcnow()

            # Close APPROVAL_PENDING workflow state
            session.query(WorkflowState).filter(
                WorkflowState.workflow_id == approval.workflow_id,
                WorkflowState.exited_at == None
            ).update({
                WorkflowState.exited_at: datetime.utcnow()
            }, synchronize_session=False)

            # Route workflow state based on approval status
            next_state = "PLANNING"  # Default fallback/rework starting point if rejected
            if status == "APPROVED":
                if approval.approval_type == "Architecture":
                    next_state = "DATABASE_DESIGN"
                elif approval.approval_type == "Security":
                    next_state = "DEPLOYING"
                elif approval.approval_type == "Deployment":
                    next_state = "COMPLETED"
                else:
                    next_state = "COMPLETED"
            else:
                # If REJECTED, route back to PLANNING or ARCHITECTING for rework
                next_state = "PLANNING"

            # Create state entry for next phase
            next_state_entry = WorkflowState(
                workflow_id=approval.workflow_id,
                state=next_state,
                entered_at=datetime.utcnow()
            )
            session.add(next_state_entry)

            # Update master workflow
            status_val = _STATE_TO_STATUS.get(next_state, "RUNNING")
            session.query(Workflow).filter(
                Workflow.workflow_id == approval.workflow_id
            ).update({
                Workflow.current_state: next_state,
                Workflow.status: status_val,
                Workflow.updated_at: datetime.utcnow()
            }, synchronize_session=False)

            session.commit()

            # Publish approval outcome
            self.event_pub.publish("approval.events", {
                "event_type": "APPROVAL_DECIDED",
                "approval_id": approval_id,
                "workflow_id": str(approval.workflow_id),
                "status": status,
                "next_state": next_state,
                "decided_at": approval.decided_at.isoformat()
            })

            logger.info(f"Processed approval outcome '{status}' for request {approval_id}. Routed workflow to '{next_state}'")
            return {
                "success": True,
                "workflow_id": str(approval.workflow_id),
                "next_state": next_state
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to process approval decision for {approval_id}: {e}")
            return {"success": False, "message": str(e)}
        finally:
            session.close()

    def check_timeouts(self) -> int:
        """
        Scans for pending approvals older than the timeout threshold (24 hours) and auto-rejects them.
        """
        session = self.SessionLocal()
        auto_reject_count = 0
        try:
            threshold = datetime.utcnow() - timedelta(hours=self.timeout_hours)
            expired_approvals = (
                session.query(Approval)
                .filter(Approval.status == "PENDING", Approval.created_at < threshold)
                .all()
            )

            for app in expired_approvals:
                logger.warning(f"Approval request {app.approval_id} expired. Performing auto-rejection timeout.")
                self.process_decision(
                    approval_id=str(app.approval_id),
                    status="REJECTED",
                    comments="Auto-rejected due to approval window timeout.",
                    user_id=str(uuid.UUID(int=0))  # System default user ID (all zeros)
                )
                auto_reject_count += 1
                
            return auto_reject_count
        except Exception as e:
            logger.error(f"Failed during approval timeout scanning: {e}")
            return 0
        finally:
            session.close()
