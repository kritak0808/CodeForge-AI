import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models import Workflow, WorkflowState, Approval, Task
from app.repositories.workflow import WorkflowRepository, ApprovalRepository, WorkflowStateRepository
from app.schemas.workflow import WorkflowCreate, ApprovalDecision
from sqlalchemy import select

logger = logging.getLogger("api-gateway.workflow-service")

# Maps LangGraph node names to the frontend-facing status string
_STATE_TO_STATUS: Dict[str, str] = {
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

_PREVIOUS_STATE: Dict[str, str] = {
    "PLANNING": "CREATED",
    "RESEARCHING": "PLANNING",
    "ARCHITECTING": "RESEARCHING",
    "DATABASE_DESIGN": "ARCHITECTING",
    "BACKEND_GENERATION": "DATABASE_DESIGN",
    "FRONTEND_GENERATION": "BACKEND_GENERATION",
    "TESTING": "FRONTEND_GENERATION",
    "SECURITY_REVIEW": "TESTING",
    "DEVOPS_GENERATION": "SECURITY_REVIEW",
    "APPROVAL_PENDING": "DEVOPS_GENERATION",
    "DEPLOYING": "APPROVAL_PENDING",
    "OBSERVABILITY": "DEPLOYING",
    "COST_OPTIMIZATION": "OBSERVABILITY",
    "AUTONOMOUS_CONTROLLER": "COST_OPTIMIZATION",
    "FINAL_DEPLOYMENT": "AUTONOMOUS_CONTROLLER",
    "COMPLETED": "FINAL_DEPLOYMENT",
}

def _derive_status(current_state: str) -> str:
    return _STATE_TO_STATUS.get(current_state, "RUNNING")

# Lazy import guard — agent-orchestrator is a separate process and may not be
# present on the API gateway's PYTHONPATH in production or during testing.
try:
    import sys
    import os
    orchestrator_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent-orchestrator")
    )
    if orchestrator_path not in sys.path:
        sys.path.insert(0, orchestrator_path)
    from workflow import build_workflow_graph as _build_workflow_graph  # noqa: F401
except Exception:
    _build_workflow_graph = None  # type: ignore[assignment]

class WorkflowService:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        approval_repo: ApprovalRepository,
        state_repo: WorkflowStateRepository
    ):
        self.workflow_repo = workflow_repo
        self.approval_repo = approval_repo
        self.state_repo = state_repo

    def _trigger_orchestrator_locally_bg(
        self,
        workflow_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        requirements: Optional[str] = None,
        target_state: Optional[str] = None,
        approval_status: Optional[str] = None
    ):
        from app.config import settings
        if not settings.KAFKA_DISABLED:
            return

        import threading
        def run_orchestrator():
            try:
                from event_publisher import KafkaEventPublisher
                from workflow_manager import WorkflowManager
                event_pub = KafkaEventPublisher()
                manager = WorkflowManager(
                    db_url=settings.DATABASE_URL,
                    redis_url=settings.REDIS_URL,
                    event_pub=event_pub
                )
                if requirements is not None:
                    manager.start_workflow(str(workflow_id), str(project_id), requirements)
                else:
                    checkpoint = manager.checkpoint_mgr.restore_checkpoint(str(workflow_id))
                    if not checkpoint:
                        checkpoint = {
                            "execution_context": {"project_id": str(project_id) if project_id else ""},
                            "agent_outputs": {},
                            "errors": []
                        }
                    
                    prev_state = _PREVIOUS_STATE.get(target_state, "CREATED")
                    ctx = checkpoint.get("execution_context", {})
                    if approval_status:
                        ctx["approval_status"] = approval_status
                        
                    state_input = {
                        "workflow_id": str(workflow_id),
                        "project_id": checkpoint.get("execution_context", {}).get("project_id", str(project_id) if project_id else ""),
                        "current_state": prev_state,
                        "current_agent": None,
                        "workflow_context": ctx,
                        "agent_outputs": checkpoint.get("agent_outputs", {}),
                        "cost_metrics": {},
                        "token_metrics": {},
                        "errors": checkpoint.get("errors", [])
                    }
                    manager.run_workflow_step(str(workflow_id), state_input)
            except Exception as e:
                logger.error(f"[Local Orchestrator BG] Failed to run step for workflow {workflow_id}: {e}")

        threading.Thread(target=run_orchestrator, daemon=True).start()

    async def trigger_workflow(self, project_id: uuid.UUID, requirements: Optional[str], user_id: uuid.UUID) -> Workflow:
        """
        Initializes a master workflow state and dispatches the execution task.
        """
        workflow_obj = Workflow(
            workflow_id=uuid.uuid4(),
            project_id=project_id,
            current_state="CREATED",
            status="CREATED",
            tasks_completed=0,
            tasks_total=0,
            triggered_by=user_id
        )
        await self.workflow_repo.create(workflow_obj)

        initial_state = WorkflowState(
            workflow_id=workflow_obj.workflow_id,
            state="CREATED",
            entered_at=datetime.utcnow()
        )
        await self.state_repo.create(initial_state)

        # Simulates async notification to Kafka event bus
        logger.info(f"Triggered workflow run {workflow_obj.workflow_id} for project {project_id}")
        self._trigger_orchestrator_locally_bg(workflow_obj.workflow_id, project_id, requirements)
        return workflow_obj

    async def get_workflow_details(self, workflow_id: uuid.UUID) -> Optional[Workflow]:
        return await self.workflow_repo.get_workflow_details(workflow_id)

    async def pause_workflow(self, workflow_id: uuid.UUID) -> Optional[Workflow]:
        """
        Pauses the workflow.
        """
        workflow = await self.workflow_repo.get(workflow_id)
        if not workflow:
            from app.exceptions import NotFoundException
            raise NotFoundException("Workflow not found")

        # Mark active state as exited
        active_state = await self.state_repo.get_active_state(workflow_id)
        if active_state:
            active_state.exited_at = datetime.utcnow()
            await self.state_repo.update(active_state, active_state)

        # Set new state
        paused_state = WorkflowState(
            workflow_id=workflow_id,
            state="PAUSED",
            entered_at=datetime.utcnow()
        )
        await self.state_repo.create(paused_state)

        workflow.current_state = "PAUSED"
        workflow.status = "PAUSED"
        workflow.updated_at = datetime.utcnow()
        await self.workflow_repo.update(workflow, workflow)

        logger.info(f"Workflow {workflow_id} paused successfully.")
        return workflow

    async def resume_workflow(self, workflow_id: uuid.UUID) -> Optional[Workflow]:
        """
        Resumes the workflow execution.
        """
        workflow = await self.workflow_repo.get(workflow_id)
        if not workflow:
            from app.exceptions import NotFoundException
            raise NotFoundException("Workflow not found")

        # Exits PAUSED state
        active_state = await self.state_repo.get_active_state(workflow_id)
        if active_state:
            active_state.exited_at = datetime.utcnow()
            await self.state_repo.update(active_state, active_state)

        # Find the state prior to PAUSED to resume from
        query = (
            select(WorkflowState)
            .filter(WorkflowState.workflow_id == workflow_id)
            .order_by(WorkflowState.entered_at.desc())
        )
        res = await self.state_repo.db.execute(query)
        states = list(res.scalars().all())
        
        resume_to = "PLANNING"  # fallback default
        for s in states:
            if s.state != "PAUSED" and s.state != "INITIATED":
                resume_to = s.state
                break

        resumed_state = WorkflowState(
            workflow_id=workflow_id,
            state=resume_to,
            entered_at=datetime.utcnow()
        )
        await self.state_repo.create(resumed_state)

        workflow.current_state = resume_to
        workflow.status = _derive_status(resume_to)
        workflow.updated_at = datetime.utcnow()
        await self.workflow_repo.update(workflow, workflow)

        logger.info(f"Workflow {workflow_id} resumed to state '{resume_to}'.")
        self._trigger_orchestrator_locally_bg(workflow_id, workflow.project_id, target_state=resume_to)
        return workflow

    async def cancel_workflow(self, workflow_id: uuid.UUID) -> Optional[Workflow]:
        """
        Cancels the workflow execution.
        """
        workflow = await self.workflow_repo.get(workflow_id)
        if not workflow:
            from app.exceptions import NotFoundException
            raise NotFoundException("Workflow not found")

        active_state = await self.state_repo.get_active_state(workflow_id)
        if active_state:
            active_state.exited_at = datetime.utcnow()
            await self.state_repo.update(active_state, active_state)

        cancelled_state = WorkflowState(
            workflow_id=workflow_id,
            state="CANCELLED",
            entered_at=datetime.utcnow()
        )
        await self.state_repo.create(cancelled_state)

        workflow.current_state = "CANCELLED"
        workflow.status = "CANCELLED"
        workflow.updated_at = datetime.utcnow()
        await self.workflow_repo.update(workflow, workflow)

        logger.info(f"Workflow {workflow_id} cancelled.")
        return workflow

    async def get_workflow_state(self, workflow_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieves the latest state representation of the workflow.
        """
        workflow = await self.workflow_repo.get(workflow_id)
        if not workflow:
            from app.exceptions import NotFoundException
            raise NotFoundException("Workflow not found")

        active_state = await self.state_repo.get_active_state(workflow_id)
        return {
            "workflow_id": str(workflow_id),
            "current_state": workflow.current_state,
            "updated_at": workflow.updated_at.isoformat(),
            "active_state_details": {
                "state_id": str(active_state.state_id) if active_state else None,
                "state": active_state.state if active_state else None,
                "metadata_json": active_state.metadata_json if active_state else None,
                "entered_at": active_state.entered_at.isoformat() if active_state else None
            } if active_state else None
        }

    async def get_workflow_logs(self, workflow_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Retrieves logs and execution trace entries of tasks executed within the workflow.
        """
        workflow = await self.workflow_repo.get_workflow_details(workflow_id)
        if not workflow:
            from app.exceptions import NotFoundException
            raise NotFoundException("Workflow not found")

        logs = []
        for task in workflow.tasks:
            logs.append({
                "task_id": str(task.task_id),
                "agent_id": task.agent_id,
                "title": task.title,
                "status": task.status,
                "timestamp": task.assigned_at.isoformat(),
                "log_message": f"Task '{task.title}' is currently {task.status}. Description: {task.description}"
            })
        return logs

    async def submit_approval_decision(
        self,
        approval_id: uuid.UUID,
        decision: ApprovalDecision,
        user_id: uuid.UUID
    ) -> Approval:
        """
        Processes human-in-the-loop decisions for pending pipeline steps.
        """
        approval = await self.approval_repo.get(approval_id)
        if not approval:
            from app.exceptions import NotFoundException
            raise NotFoundException("Approval request not found")

        if approval.status != "PENDING":
            from app.exceptions import ConflictException
            raise ConflictException("This approval request has already been decided")

        # Update Approval record
        approval.status = decision.status
        approval.comments = decision.comments
        approval.approver_id = user_id
        approval.decided_at = datetime.utcnow()
        await self.approval_repo.update(approval, approval)

        # Route workflow state based on decision status
        next_state = "PLANNING"
        if decision.status == "APPROVED":
            if approval.approval_type == "Architecture":
                next_state = "DATABASE_DESIGN"
            elif approval.approval_type == "Security":
                next_state = "DEPLOYING"
            elif approval.approval_type == "Deployment":
                next_state = "COMPLETED"
            else:
                next_state = "COMPLETED"

        # Update master workflow state
        workflow = await self.workflow_repo.get(approval.workflow_id)
        if workflow:
            active_state = await self.state_repo.get_active_state(workflow.workflow_id)
            if active_state:
                active_state.exited_at = datetime.utcnow()
                await self.state_repo.update(active_state, active_state)

            new_state_entry = WorkflowState(
                workflow_id=workflow.workflow_id,
                state=next_state,
                entered_at=datetime.utcnow()
            )
            await self.state_repo.create(new_state_entry)

            workflow.current_state = next_state
            workflow.status = _derive_status(next_state)
            workflow.updated_at = datetime.utcnow()
            await self.workflow_repo.update(workflow, workflow)

        logger.info(f"Human-in-the-loop approval decision submitted: {decision.status} for approval {approval_id}")
        self._trigger_orchestrator_locally_bg(
            workflow.workflow_id,
            workflow.project_id,
            target_state=next_state,
            approval_status=decision.status
        )
        return approval

    async def approve_workflow_step(self, workflow_id: uuid.UUID, user_id: uuid.UUID, comments: Optional[str] = None) -> Approval:
        """
        Approve the current step of a workflow.
        """
        query = (
            select(Approval)
            .filter(Approval.workflow_id == workflow_id, Approval.status == "PENDING")
            .order_by(Approval.created_at.desc())
        )
        res = await self.approval_repo.db.execute(query)
        approval = res.scalars().first()
        if not approval:
            from app.exceptions import NotFoundException
            raise NotFoundException("No pending approval found for this workflow")

        decision = ApprovalDecision(status="APPROVED", comments=comments)
        return await self.submit_approval_decision(approval.approval_id, decision, user_id)

    async def reject_workflow_step(self, workflow_id: uuid.UUID, user_id: uuid.UUID, comments: Optional[str] = None) -> Approval:
        """
        Reject the current step of a workflow.
        """
        query = (
            select(Approval)
            .filter(Approval.workflow_id == workflow_id, Approval.status == "PENDING")
            .order_by(Approval.created_at.desc())
        )
        res = await self.approval_repo.db.execute(query)
        approval = res.scalars().first()
        if not approval:
            from app.exceptions import NotFoundException
            raise NotFoundException("No pending approval found for this workflow")

        decision = ApprovalDecision(status="REJECTED", comments=comments)
        return await self.submit_approval_decision(approval.approval_id, decision, user_id)

