"""
ObservabilityService – orchestrates persistence of Observability Platform artifacts,
triggers Kafka events for workflow orchestration, and exposes read helpers
for the REST layer.
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
    ObservabilityGeneration,
    AgentMetric,
    WorkflowMetric,
    ApiMetric,
    SystemMetric,
    ErrorEvent,
    AlertRule,
    AlertEvent,
)
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
from app.schemas.observability import ObservabilityGenerationPayload

# ── Kafka Event Publisher ─────────────────────────────────────────────────────
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

logger = logging.getLogger("api-gateway.observability-service")


class ObservabilityService:
    """
    Service layer for the Observability & Monitoring Platform Agent.
    """

    def __init__(
        self,
        generation_repo: ObservabilityGenerationRepository,
        agent_metric_repo: AgentMetricRepository,
        workflow_metric_repo: WorkflowMetricRepository,
        api_metric_repo: ApiMetricRepository,
        system_metric_repo: SystemMetricRepository,
        error_event_repo: ErrorEventRepository,
        alert_rule_repo: AlertRuleRepository,
        alert_event_repo: AlertEventRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.agent_metric_repo = agent_metric_repo
        self.workflow_metric_repo = workflow_metric_repo
        self.api_metric_repo = api_metric_repo
        self.system_metric_repo = system_metric_repo
        self.error_event_repo = error_event_repo
        self.alert_rule_repo = alert_rule_repo
        self.alert_event_repo = alert_event_repo
        self.db = db

        self._event_pub = None
        from app.config import settings as _svc_settings
        if _kafka_available and not _svc_settings.KAFKA_DISABLED:
            try:
                self._event_pub = KafkaEventPublisher()
            except Exception as exc:
                logger.warning(f"Kafka publisher unavailable: {exc}")

    # ── Write path ────────────────────────────────────────────────────────────

    async def trigger_generation(
        self,
        project_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> ObservabilityGeneration:
        """
        Creates a PENDING ObservabilityGeneration record and publishes
        observability.started so the agent worker picks it up.
        """
        gen = ObservabilityGeneration(
            generation_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            status="PENDING",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.commit()
        await self.db.refresh(gen)

        self._publish_event(
            "observability.started",
            {
                "event_type": "observability.started",
                "generation_id": str(gen.generation_id),
                "project_id": str(project_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"ObservabilityGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: ObservabilityGenerationPayload
    ) -> ObservabilityGeneration:
        """
        Called by the agent worker after the ObservabilityAgent pipeline completes.
        Atomically persists all 7 child metric types and fires the
        observability.completed Kafka event.
        """
        gen = ObservabilityGeneration(
            generation_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            status="COMPLETED",
            notes=payload.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.flush()

        # 1. Agent Metrics
        for am in payload.agent_metrics:
            self.db.add(AgentMetric(
                metric_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                agent_name=am.agent_name,
                duration_ms=am.duration_ms,
                tokens_used=am.tokens_used,
                success_rate=am.success_rate,
                error_count=am.error_count,
                extra_metadata=am.extra_metadata,
                recorded_at=datetime.utcnow(),
            ))

        # 2. Workflow Metrics
        for wm in payload.workflow_metrics:
            self.db.add(WorkflowMetric(
                metric_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                workflow_id=wm.workflow_id,
                step_name=wm.step_name,
                duration_ms=wm.duration_ms,
                status=wm.status,
                throughput_rps=wm.throughput_rps,
                recorded_at=datetime.utcnow(),
            ))

        # 3. API Metrics
        for apm in payload.api_metrics:
            self.db.add(ApiMetric(
                metric_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                endpoint=apm.endpoint,
                method=apm.method,
                avg_latency_ms=apm.avg_latency_ms,
                p99_latency_ms=apm.p99_latency_ms,
                error_rate=apm.error_rate,
                request_count=apm.request_count,
                recorded_at=datetime.utcnow(),
            ))

        # 4. System Metrics
        for sm in payload.system_metrics:
            self.db.add(SystemMetric(
                metric_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                service_name=sm.service_name,
                cpu_pct=sm.cpu_pct,
                memory_pct=sm.memory_pct,
                disk_pct=sm.disk_pct,
                recorded_at=datetime.utcnow(),
            ))

        # 5. Error Events
        for ee in payload.error_events:
            self.db.add(ErrorEvent(
                event_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                source=ee.source,
                severity=ee.severity,
                message=ee.message,
                stack_trace=ee.stack_trace,
                context=ee.context,
                occurred_at=datetime.utcnow(),
            ))

        # 6. Alert Rules
        rule_id_map: dict[str, uuid.UUID] = {}
        for ar in payload.alert_rules:
            rule_id = uuid.uuid4()
            rule_id_map[ar.rule_name] = rule_id
            self.db.add(AlertRule(
                rule_id=rule_id,
                generation_id=gen.generation_id,
                rule_name=ar.rule_name,
                metric_name=ar.metric_name,
                operator=ar.operator,
                threshold=ar.threshold,
                severity=ar.severity,
                is_active=ar.is_active,
                created_at=datetime.utcnow(),
            ))

        # Flush so alert_rules exist before alert_events FK
        await self.db.flush()

        # 7. Alert Events
        for ae in payload.alert_events:
            rule_id = rule_id_map.get(ae.rule_name)
            self.db.add(AlertEvent(
                alert_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                rule_id=rule_id,
                rule_name=ae.rule_name,
                current_value=ae.current_value,
                threshold=ae.threshold,
                severity=ae.severity,
                message=ae.message,
                status=ae.status,
                fired_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event
        self._publish_event(
            "observability.generation.events",
            {
                "event_type": "observability.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"ObservabilityGeneration persisted: generation_id={gen.generation_id} "
            f"agent_metrics={len(payload.agent_metrics)} "
            f"error_events={len(payload.error_events)} "
            f"alert_events={len(payload.alert_events)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Marks the generation as SUPERSEDED and republishes observability.started.
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "observability.started",
            {
                "event_type": "observability.started",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Observability regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[ObservabilityGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ObservabilityGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_agent_metrics(
        self, generation_id: uuid.UUID
    ) -> List[AgentMetric]:
        return await self.agent_metric_repo.list_by_generation(generation_id)

    async def list_workflow_metrics(
        self, generation_id: uuid.UUID
    ) -> List[WorkflowMetric]:
        return await self.workflow_metric_repo.list_by_generation(generation_id)

    async def list_api_metrics(
        self, generation_id: uuid.UUID
    ) -> List[ApiMetric]:
        return await self.api_metric_repo.list_by_generation(generation_id)

    async def list_system_metrics(
        self, generation_id: uuid.UUID
    ) -> List[SystemMetric]:
        return await self.system_metric_repo.list_by_generation(generation_id)

    async def list_error_events(
        self, generation_id: uuid.UUID
    ) -> List[ErrorEvent]:
        return await self.error_event_repo.list_by_generation(generation_id)

    async def list_alert_rules(
        self, generation_id: uuid.UUID
    ) -> List[AlertRule]:
        return await self.alert_rule_repo.list_by_generation(generation_id)

    async def list_alert_events(
        self, generation_id: uuid.UUID
    ) -> List[AlertEvent]:
        return await self.alert_event_repo.list_by_generation(generation_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
