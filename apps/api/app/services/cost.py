"""
CostOptimizationService – orchestrates persistence of Cost Optimization artifacts,
triggers Kafka events, and exposes read helpers for the REST layer.
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
    CostGeneration,
    CostReport,
    ResourceUsageMetric,
    OptimizationRecommendation,
    SavingsEstimate,
    BudgetPolicy,
    CostAlert,
)
from app.repositories.cost import (
    CostGenerationRepository,
    CostReportRepository,
    ResourceUsageMetricRepository,
    OptimizationRecommendationRepository,
    SavingsEstimateRepository,
    BudgetPolicyRepository,
    CostAlertRepository,
)
from app.schemas.cost import CostGenerationPayload, BudgetPolicyRequest

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

logger = logging.getLogger("api-gateway.cost-optimization-service")


class CostOptimizationService:
    """
    Service layer for the Cost Optimization Agent.
    """

    def __init__(
        self,
        generation_repo: CostGenerationRepository,
        report_repo: CostReportRepository,
        metric_repo: ResourceUsageMetricRepository,
        recommendation_repo: OptimizationRecommendationRepository,
        savings_repo: SavingsEstimateRepository,
        policy_repo: BudgetPolicyRepository,
        alert_repo: CostAlertRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.report_repo = report_repo
        self.metric_repo = metric_repo
        self.recommendation_repo = recommendation_repo
        self.savings_repo = savings_repo
        self.policy_repo = policy_repo
        self.alert_repo = alert_repo
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
    ) -> CostGeneration:
        """
        Creates a PENDING CostGeneration record and publishes cost.started.
        """
        gen = CostGeneration(
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

        self._publish("cost.started", {
            "event_type": "cost.started",
            "generation_id": str(gen.generation_id),
            "project_id": str(project_id),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"CostGeneration triggered: generation_id={gen.generation_id}")
        return gen

    async def create_generation_from_payload(
        self, payload: CostGenerationPayload
    ) -> CostGeneration:
        """
        Called by the agent worker after analysis is complete.
        Atomically persists all child records and fires cost.analysis.completed.
        """
        gen = CostGeneration(
            generation_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            status="COMPLETED",
            total_cost=payload.total_cost,
            estimated_monthly_cost=payload.estimated_monthly_cost,
            currency=payload.currency,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.flush()

        # 1. Cost reports
        for cr in payload.cost_reports:
            self.db.add(CostReport(
                report_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                category=cr.category,
                current_cost=cr.current_cost,
                projected_cost=cr.projected_cost,
                notes=cr.notes,
                created_at=datetime.utcnow(),
            ))

        # 2. Resource usage metrics
        for rum in payload.resource_usage_metrics:
            self.db.add(ResourceUsageMetric(
                metric_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                resource_type=rum.resource_type,
                utilization_percent=rum.utilization_percent,
                consumption=rum.consumption,
                unit=rum.unit,
                recorded_at=datetime.utcnow(),
            ))

        # 3. Optimization recommendations
        for rec in payload.optimization_recommendations:
            self.db.add(OptimizationRecommendation(
                recommendation_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                title=rec.title,
                description=rec.description,
                impact_level=rec.impact_level,
                estimated_savings=rec.estimated_savings,
                category=rec.category,
                created_at=datetime.utcnow(),
            ))

        # 4. Savings estimates
        for se in payload.savings_estimates:
            self.db.add(SavingsEstimate(
                estimate_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                monthly_savings=se.monthly_savings,
                annual_savings=se.annual_savings,
                confidence_level=se.confidence_level,
                assumptions=se.assumptions,
                created_at=datetime.utcnow(),
            ))

        # 5. Cost alerts
        for ca in payload.cost_alerts:
            self.db.add(CostAlert(
                alert_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                policy_id=None,
                severity=ca.severity,
                message=ca.message,
                current_cost=ca.current_cost,
                budget_limit=ca.budget_limit,
                status=ca.status,
                fired_at=datetime.utcnow(),
            ))
            if ca.status == "OPEN":
                self._publish("cost.alert", {
                    "event_type": "cost.alert",
                    "generation_id": str(gen.generation_id),
                    "severity": ca.severity,
                    "message": ca.message,
                    "current_cost": ca.current_cost,
                    "budget_limit": ca.budget_limit,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        await self.db.commit()
        await self.db.refresh(gen)

        self._publish("cost.generation.events", {
            "event_type": "cost.analysis.completed",
            "generation_id": str(gen.generation_id),
            "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
            "project_id": str(payload.project_id),
            "total_cost": payload.total_cost,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._publish("cost.generation.events", {
            "event_type": "cost.optimization.generated",
            "generation_id": str(gen.generation_id),
            "recommendation_count": len(payload.optimization_recommendations),
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(
            f"CostGeneration persisted: generation_id={gen.generation_id} "
            f"total_cost={payload.total_cost} recommendations={len(payload.optimization_recommendations)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish("cost.started", {
            "event_type": "cost.started",
            "generation_id": str(generation_id),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def upsert_budget_policy(
        self, req: BudgetPolicyRequest
    ) -> BudgetPolicy:
        """
        Creates or deactivates existing policies and creates a new active one.
        """
        # Deactivate any existing active policy for this project
        existing = await self.policy_repo.get_by_project(req.project_id)
        if existing:
            existing.is_active = False
            await self.db.flush()

        policy = BudgetPolicy(
            policy_id=uuid.uuid4(),
            project_id=req.project_id,
            monthly_budget=req.monthly_budget,
            alert_threshold=req.alert_threshold,
            currency=req.currency,
            is_active=req.is_active,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(self, generation_id: uuid.UUID) -> Optional[CostGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[CostGeneration]:
        return await self.generation_repo.list_by_project(project_id, skip=skip, limit=limit)

    async def list_reports(self, generation_id: uuid.UUID) -> List[CostReport]:
        return await self.report_repo.list_by_generation(generation_id)

    async def list_metrics(self, generation_id: uuid.UUID) -> List[ResourceUsageMetric]:
        return await self.metric_repo.list_by_generation(generation_id)

    async def list_recommendations(
        self, generation_id: uuid.UUID
    ) -> List[OptimizationRecommendation]:
        return await self.recommendation_repo.list_by_generation(generation_id)

    async def list_savings(self, generation_id: uuid.UUID) -> List[SavingsEstimate]:
        return await self.savings_repo.list_by_generation(generation_id)

    async def list_alerts(self, generation_id: uuid.UUID) -> List[CostAlert]:
        return await self.alert_repo.list_by_generation(generation_id)

    async def get_budget_policy(self, project_id: uuid.UUID) -> Optional[BudgetPolicy]:
        return await self.policy_repo.get_by_project(project_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
