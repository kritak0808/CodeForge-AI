"""
AutonomousControllerService – coordinates persistence, triggers Kafka events,
and exposes API/worker helpers for the Autonomous SDLC Controller (Milestone 17).
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AutonomousController,
    WorkflowDecision,
    AgentHealth,
    RetryHistory,
    FailureEvent,
    RollbackEvent,
    ExecutionPlan,
    ControllerLog,
)
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
from app.schemas.controller import (
    AutonomousControllerPayload,
    AgentHealthPayload,
)

# ── Kafka publisher ───────────────────────────────────────────────────────────
orchestrator_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent-orchestrator")
)
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

try:
    from event_publisher import KafkaEventPublisher
    _kafka_available = True
except ImportError:
    _kafka_available = False

logger = logging.getLogger("api-gateway.autonomous-controller-service")


class AutonomousControllerService:
    """
    Service layer coordinating the Autonomous SDLC Controller run cycles.
    """

    def __init__(
        self,
        controller_repo: AutonomousControllerRepository,
        decision_repo: WorkflowDecisionRepository,
        health_repo: AgentHealthRepository,
        retry_repo: RetryHistoryRepository,
        failure_repo: FailureEventRepository,
        rollback_repo: RollbackEventRepository,
        plan_repo: ExecutionPlanRepository,
        log_repo: ControllerLogRepository,
        db: AsyncSession,
    ):
        self.controller_repo = controller_repo
        self.decision_repo = decision_repo
        self.health_repo = health_repo
        self.retry_repo = retry_repo
        self.failure_repo = failure_repo
        self.rollback_repo = rollback_repo
        self.plan_repo = plan_repo
        self.log_repo = log_repo
        self.db = db

        self._event_pub = None
        from app.config import settings as _svc_settings
        if _kafka_available and not _svc_settings.KAFKA_DISABLED:
            try:
                self._event_pub = KafkaEventPublisher()
            except Exception as exc:
                logger.warning(f"Kafka publisher unavailable: {exc}")

    def _publish(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Offline] Would publish to '{topic}': {payload}")

    # ── Write Path ────────────────────────────────────────────────────────────

    async def trigger_controller(
        self,
        project_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> AutonomousController:
        """
        Creates a root controller execution and generates an initial plan.
        """
        ctrl = AutonomousController(
            controller_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            status="ACTIVE",
            current_step="AUTONOMOUS_CONTROLLER",
            budget_limit=1000.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(ctrl)
        await self.db.flush()

        # Add initial ExecutionPlan
        plan = ExecutionPlan(
            plan_id=uuid.uuid4(),
            controller_id=ctrl.controller_id,
            workflow_id=workflow_id or uuid.uuid4(),
            steps_json=["PLANNING", "RESEARCHING", "ARCHITECTING", "DATABASE_DESIGN", "BACKEND_GENERATION", "FRONTEND_GENERATION", "TESTING", "SECURITY_REVIEW", "DEVOPS_GENERATION", "DEPLOYING", "OBSERVABILITY", "COST_OPTIMIZATION", "AUTONOMOUS_CONTROLLER", "FINAL_DEPLOYMENT"],
            current_step_index=12,  # We are currently at AUTONOMOUS_CONTROLLER
            is_optimized=False,
            created_at=datetime.utcnow(),
        )
        self.db.add(plan)

        # Log initiation
        log = ControllerLog(
            log_id=uuid.uuid4(),
            controller_id=ctrl.controller_id,
            workflow_id=workflow_id or uuid.uuid4(),
            level="INFO",
            message="Autonomous Controller run initiated.",
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(ctrl)

        self._publish("controller.started", {
            "event_type": "controller.started",
            "controller_id": str(ctrl.controller_id),
            "project_id": str(project_id),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ctrl

    async def create_controller_from_payload(
        self, payload: AutonomousControllerPayload
    ) -> AutonomousController:
        """
        Ingests the controller decision outcome payload produced by the agent worker.
        """
        ctrl = AutonomousController(
            controller_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            status=payload.status,
            current_step=payload.current_step,
            budget_limit=payload.budget_limit,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(ctrl)
        await self.db.flush()

        # Decisions
        for d in payload.decisions:
            dec = WorkflowDecision(
                decision_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                step=d.step,
                decision_type=d.decision_type,
                reason=d.reason,
                action_taken=d.action_taken,
                metadata_json=d.metadata_json,
                created_at=datetime.utcnow(),
            )
            self.db.add(dec)
            # Emit Kafka event on decision
            self._publish("controller.decision", {
                "event_type": "controller.decision",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "step": d.step,
                "decision_type": d.decision_type,
                "action_taken": d.action_taken,
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Retries
        for r in payload.retries:
            self.db.add(RetryHistory(
                retry_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                step=r.step,
                retry_attempt=r.retry_attempt,
                max_retries=r.max_retries,
                error_message=r.error_message,
                next_retry_at=r.next_retry_at,
                created_at=datetime.utcnow(),
            ))

        # Failures
        for f in payload.failures:
            self.db.add(FailureEvent(
                failure_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                step=f.step,
                error_type=f.error_type,
                error_message=f.error_message,
                severity=f.severity,
                is_resolved=f.is_resolved,
                created_at=datetime.utcnow(),
            ))

        # Rollbacks
        for rb in payload.rollbacks:
            self.db.add(RollbackEvent(
                rollback_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                source_step=rb.source_step,
                target_step=rb.target_step,
                reason=rb.reason,
                status=rb.status,
                created_at=datetime.utcnow(),
            ))

        # Plans
        for p in payload.execution_plans:
            self.db.add(ExecutionPlan(
                plan_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                steps_json=p.steps_json,
                current_step_index=p.current_step_index,
                is_optimized=p.is_optimized,
                created_at=datetime.utcnow(),
            ))

        # Logs
        for l in payload.logs:
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=payload.workflow_id or uuid.uuid4(),
                level=l.level,
                message=l.message,
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(ctrl)

        # Publish final completion or fail state
        if ctrl.status == "COMPLETED":
            self._publish("controller.completed", {
                "event_type": "controller.completed",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            })
        elif ctrl.status == "FAILED":
            self._publish("controller.failed", {
                "event_type": "controller.failed",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "error": "Controller evaluation failed.",
                "timestamp": datetime.utcnow().isoformat(),
            })

        return ctrl

    # ── Interactive Control Methods ───────────────────────────────────────────

    async def pause_execution(self, workflow_id: uuid.UUID) -> Optional[AutonomousController]:
        ctrl = await self.controller_repo.get_by_workflow(workflow_id)
        if ctrl:
            ctrl.status = "PAUSED"
            ctrl.updated_at = datetime.utcnow()
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                level="WARNING",
                message="Workflow execution manually PAUSED.",
                created_at=datetime.utcnow(),
            ))
            await self.db.commit()
            await self.db.refresh(ctrl)
        return ctrl

    async def resume_execution(self, workflow_id: uuid.UUID) -> Optional[AutonomousController]:
        ctrl = await self.controller_repo.get_by_workflow(workflow_id)
        if ctrl:
            ctrl.status = "ACTIVE"
            ctrl.updated_at = datetime.utcnow()
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                level="INFO",
                message="Workflow execution manually RESUMED.",
                created_at=datetime.utcnow(),
            ))
            await self.db.commit()
            await self.db.refresh(ctrl)
        return ctrl

    async def retry_step(self, workflow_id: uuid.UUID, step: str) -> Optional[AutonomousController]:
        ctrl = await self.controller_repo.get_by_workflow(workflow_id)
        if ctrl:
            ctrl.status = "ACTIVE"
            ctrl.updated_at = datetime.utcnow()
            # Log decision
            dec = WorkflowDecision(
                decision_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                step=step,
                decision_type="RETRY",
                reason="Manual retry request",
                action_taken="Scheduling retry of step",
                created_at=datetime.utcnow(),
            )
            self.db.add(dec)
            # Log entry
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                level="INFO",
                message=f"Manual retry initiated for step: {step}",
                created_at=datetime.utcnow(),
            ))
            await self.db.commit()
            await self.db.refresh(ctrl)

            # Publish retry event
            self._publish("controller.retry", {
                "event_type": "controller.retry",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(workflow_id),
                "step": step,
                "timestamp": datetime.utcnow().isoformat(),
            })
        return ctrl

    async def rollback_step(
        self, workflow_id: uuid.UUID, target_step: str, reason: str
    ) -> Optional[AutonomousController]:
        ctrl = await self.controller_repo.get_by_workflow(workflow_id)
        if ctrl:
            ctrl.status = "ACTIVE"
            ctrl.updated_at = datetime.utcnow()
            # Register RollbackEvent
            self.db.add(RollbackEvent(
                rollback_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                source_step=ctrl.current_step,
                target_step=target_step,
                reason=reason,
                status="COMPLETED",
                created_at=datetime.utcnow(),
            ))
            # Log decision
            dec = WorkflowDecision(
                decision_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                step=target_step,
                decision_type="ROLLBACK",
                reason=reason,
                action_taken=f"Rolling back to: {target_step}",
                created_at=datetime.utcnow(),
            )
            self.db.add(dec)
            # Log entry
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                level="WARNING",
                message=f"Manual rollback triggered to step: {target_step}. Reason: {reason}",
                created_at=datetime.utcnow(),
            ))
            await self.db.commit()
            await self.db.refresh(ctrl)

            # Publish rollback event
            self._publish("controller.rollback", {
                "event_type": "controller.rollback",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(workflow_id),
                "target_step": target_step,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            })
        return ctrl

    async def cancel_execution(self, workflow_id: uuid.UUID) -> Optional[AutonomousController]:
        ctrl = await self.controller_repo.get_by_workflow(workflow_id)
        if ctrl:
            ctrl.status = "CANCELLED"
            ctrl.updated_at = datetime.utcnow()
            self.db.add(ControllerLog(
                log_id=uuid.uuid4(),
                controller_id=ctrl.controller_id,
                workflow_id=workflow_id,
                level="ERROR",
                message="Workflow execution manually CANCELLED.",
                created_at=datetime.utcnow(),
            ))
            await self.db.commit()
            await self.db.refresh(ctrl)

            # Publish fail event
            self._publish("controller.failed", {
                "event_type": "controller.failed",
                "controller_id": str(ctrl.controller_id),
                "workflow_id": str(workflow_id),
                "project_id": str(ctrl.project_id),
                "error": "Execution cancelled manually.",
                "timestamp": datetime.utcnow().isoformat(),
            })
        return ctrl

    # ── Read Path ─────────────────────────────────────────────────────────────

    async def get_controller(self, controller_id: uuid.UUID) -> Optional[AutonomousController]:
        return await self.controller_repo.get(controller_id)

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[AutonomousController]:
        return await self.controller_repo.get_by_workflow(workflow_id)

    async def list_decisions(self, controller_id: uuid.UUID) -> List[WorkflowDecision]:
        return await self.decision_repo.list_by_controller(controller_id)

    async def list_failures(self, controller_id: uuid.UUID) -> List[FailureEvent]:
        return await self.failure_repo.list_by_controller(controller_id)

    async def list_rollbacks(self, controller_id: uuid.UUID) -> List[RollbackEvent]:
        return await self.rollback_repo.list_by_controller(controller_id)

    async def list_retries(self, controller_id: uuid.UUID) -> List[RetryHistory]:
        return await self.retry_repo.list_by_controller(controller_id)

    async def list_logs(self, controller_id: uuid.UUID) -> List[ControllerLog]:
        return await self.log_repo.list_by_controller(controller_id)

    async def get_plan(self, controller_id: uuid.UUID) -> Optional[ExecutionPlan]:
        return await self.plan_repo.get_by_controller(controller_id)

    async def get_agent_health(self, agent_id: str) -> Optional[AgentHealth]:
        return await self.health_repo.get_by_agent(agent_id)

    async def list_agent_health(self) -> List[AgentHealth]:
        return await self.health_repo.list_all()

    async def upsert_agent_health(self, payload: AgentHealthPayload) -> AgentHealth:
        health = await self.health_repo.get_by_agent(payload.agent_id)
        if not health:
            health = AgentHealth(
                health_id=uuid.uuid4(),
                agent_id=payload.agent_id,
                status=payload.status,
                last_heartbeat=datetime.utcnow(),
                error_count=payload.error_count,
                avg_response_time=payload.avg_response_time,
                metadata_json=payload.metadata_json,
            )
            self.db.add(health)
        else:
            health.status = payload.status
            health.last_heartbeat = datetime.utcnow()
            health.error_count = payload.error_count
            health.avg_response_time = payload.avg_response_time
            health.metadata_json = payload.metadata_json
        await self.db.commit()
        return health
