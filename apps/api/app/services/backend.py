"""
BackendGenerationService – orchestrates persistence of Backend Agent artifacts,
triggers Kafka events for workflow orchestration, and exposes read helpers
for the REST layer.

All database operations use async/await to match the AsyncSession pattern.
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
    BackendGeneration,
    ApiEndpoint,
    ServiceDefinition,
    RepositoryDefinition,
    BusinessRule,
    ApiTestReport,
)
from app.repositories.backend import (
    BackendGenerationRepository,
    ApiEndpointRepository,
    ServiceDefinitionRepository,
    RepositoryDefinitionRepository,
    BusinessRuleRepository,
    ApiTestReportRepository,
)
from app.schemas.backend import BackendGenerationPayload

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

logger = logging.getLogger("api-gateway.backend-service")


class BackendGenerationService:
    """
    Service layer for the Backend Agent.

    Responsibilities:
    - Trigger backend generation by publishing a Kafka event.
    - Atomically persist BackendGeneration root + all 5 child artifact types.
    - Publish backend.generation.completed → orchestrator resumes workflow.
    - Expose read helpers for the REST router layer.
    """

    def __init__(
        self,
        generation_repo: BackendGenerationRepository,
        endpoint_repo: ApiEndpointRepository,
        service_repo: ServiceDefinitionRepository,
        repository_repo: RepositoryDefinitionRepository,
        rule_repo: BusinessRuleRepository,
        test_repo: ApiTestReportRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.endpoint_repo = endpoint_repo
        self.service_repo = service_repo
        self.repository_repo = repository_repo
        self.rule_repo = rule_repo
        self.test_repo = test_repo
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
        workflow_id: uuid.UUID,
        design_id: Optional[uuid.UUID] = None,
        report_id: Optional[uuid.UUID] = None,
        framework: str = "FastAPI",
        language: str = "Python",
    ) -> BackendGeneration:
        """
        Creates a PENDING BackendGeneration record and publishes
        backend.generation.requested so the agent worker picks it up.
        """
        gen = BackendGeneration(
            generation_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            design_id=design_id,
            report_id=report_id,
            status="PENDING",
            framework=framework,
            language=language,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.commit()
        await self.db.refresh(gen)

        self._publish_event(
            "backend.generation.requested",
            {
                "event_type": "backend.generation.requested",
                "generation_id": str(gen.generation_id),
                "project_id": str(project_id),
                "workflow_id": str(workflow_id),
                "design_id": str(design_id) if design_id else None,
                "report_id": str(report_id) if report_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"BackendGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: BackendGenerationPayload
    ) -> BackendGeneration:
        """
        Called by the agent worker after the BackendAgent pipeline completes.
        Atomically persists all 5 artifact child types and fires the
        backend.generation.completed Kafka event.
        """
        gen = BackendGeneration(
            generation_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            design_id=payload.design_id,
            report_id=payload.report_id,
            status="COMPLETED",
            framework=payload.framework,
            language=payload.language,
            openapi_spec=payload.openapi_spec,
            notes=payload.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.flush()  # obtain generation_id before children

        # 1. API endpoints
        for ep in payload.endpoints:
            self.db.add(ApiEndpoint(
                endpoint_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                method=ep.method,
                path=ep.path,
                summary=ep.summary,
                request_schema=ep.request_schema,
                response_schema=ep.response_schema,
                router_code=ep.router_code,
                auth_required=ep.auth_required,
                rate_limited=ep.rate_limited,
                created_at=datetime.utcnow(),
            ))

        # 2. Service definitions
        for svc in payload.services:
            self.db.add(ServiceDefinition(
                service_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                service_name=svc.service_name,
                description=svc.description,
                code=svc.code,
                dependencies=svc.dependencies,
                created_at=datetime.utcnow(),
            ))

        # 3. Repository definitions
        for repo in payload.repositories:
            self.db.add(RepositoryDefinition(
                repo_def_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                repo_name=repo.repo_name,
                model_name=repo.model_name,
                code=repo.code,
                created_at=datetime.utcnow(),
            ))

        # 4. Business rules
        for rule in payload.rules:
            self.db.add(BusinessRule(
                rule_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                rule_name=rule.rule_name,
                description=rule.description,
                rule_type=rule.rule_type,
                code=rule.code,
                created_at=datetime.utcnow(),
            ))

        # 5. Test reports
        for test in payload.test_reports:
            self.db.add(ApiTestReport(
                test_report_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                test_type=test.test_type,
                test_name=test.test_name,
                test_code=test.test_code,
                status="GENERATED",
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event → orchestrator resumes workflow
        self._publish_event(
            "backend.generation.completed",
            {
                "event_type": "backend.generation.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"BackendGeneration persisted: generation_id={gen.generation_id} "
            f"endpoints={len(payload.endpoints)} services={len(payload.services)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the generation as SUPERSEDED and republish backend.generation.requested
        so the agent worker will perform a fresh generation run.
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "backend.generation.requested",
            {
                "event_type": "backend.generation.requested",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Backend regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[BackendGeneration]:
        return await self.generation_repo.get(generation_id)

    async def get_full_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[BackendGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BackendGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_endpoints(
        self, generation_id: uuid.UUID
    ) -> List[ApiEndpoint]:
        return await self.endpoint_repo.list_by_generation(generation_id)

    async def list_services(
        self, generation_id: uuid.UUID
    ) -> List[ServiceDefinition]:
        return await self.service_repo.list_by_generation(generation_id)

    async def list_repositories(
        self, generation_id: uuid.UUID
    ) -> List[RepositoryDefinition]:
        return await self.repository_repo.list_by_generation(generation_id)

    async def list_rules(
        self,
        generation_id: uuid.UUID,
        *,
        rule_type: Optional[str] = None,
    ) -> List[BusinessRule]:
        return await self.rule_repo.list_by_generation(
            generation_id, rule_type=rule_type
        )

    async def list_tests(
        self,
        generation_id: uuid.UUID,
        *,
        test_type: Optional[str] = None,
    ) -> List[ApiTestReport]:
        return await self.test_repo.list_by_generation(
            generation_id, test_type=test_type
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
