"""
FrontendGenerationService – orchestrates persistence of Frontend Agent artifacts,
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
    FrontendGeneration,
    FrontendPage,
    FrontendComponent,
    FrontendForm,
    FrontendHook,
    FrontendTestReport,
    UiDesignArtifact,
)
from app.repositories.frontend import (
    FrontendGenerationRepository,
    FrontendPageRepository,
    FrontendComponentRepository,
    FrontendFormRepository,
    FrontendHookRepository,
    FrontendTestReportRepository,
    UiDesignArtifactRepository,
)
from app.schemas.frontend import FrontendGenerationPayload

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

logger = logging.getLogger("api-gateway.frontend-service")


class FrontendGenerationService:
    """
    Service layer for the Frontend Agent.
    """

    def __init__(
        self,
        generation_repo: FrontendGenerationRepository,
        page_repo: FrontendPageRepository,
        component_repo: FrontendComponentRepository,
        form_repo: FrontendFormRepository,
        hook_repo: FrontendHookRepository,
        test_repo: FrontendTestReportRepository,
        ui_design_artifact_repo: UiDesignArtifactRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.page_repo = page_repo
        self.component_repo = component_repo
        self.form_repo = form_repo
        self.hook_repo = hook_repo
        self.test_repo = test_repo
        self.ui_design_artifact_repo = ui_design_artifact_repo
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
        backend_generation_id: Optional[uuid.UUID] = None,
        design_id: Optional[uuid.UUID] = None,
        report_id: Optional[uuid.UUID] = None,
        framework: str = "Next.js 15",
        language: str = "TypeScript",
    ) -> FrontendGeneration:
        """
        Creates a PENDING FrontendGeneration record and publishes
        frontend.generation.requested so the agent worker picks it up.
        """
        gen = FrontendGeneration(
            generation_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            backend_generation_id=backend_generation_id,
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
            "frontend.generation.requested",
            {
                "event_type": "frontend.generation.requested",
                "generation_id": str(gen.generation_id),
                "project_id": str(project_id),
                "workflow_id": str(workflow_id),
                "backend_generation_id": str(backend_generation_id) if backend_generation_id else None,
                "design_id": str(design_id) if design_id else None,
                "report_id": str(report_id) if report_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"FrontendGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: FrontendGenerationPayload
    ) -> FrontendGeneration:
        """
        Called by the agent worker after the FrontendAgent pipeline completes.
        Atomically persists all child artifact types and fires the
        frontend.generation.completed Kafka event.
        """
        gen = FrontendGeneration(
            generation_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            backend_generation_id=payload.backend_generation_id,
            design_id=payload.design_id,
            report_id=payload.report_id,
            status="COMPLETED",
            framework=payload.framework,
            language=payload.language,
            notes=payload.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.flush()

        # 1. Pages
        for pg in payload.pages:
            self.db.add(FrontendPage(
                page_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                page_type=pg.page_type,
                route_path=pg.route_path,
                code=pg.code,
                metadata_json=pg.metadata_json,
                created_at=datetime.utcnow(),
            ))

        # 2. Components
        for comp in payload.components:
            self.db.add(FrontendComponent(
                component_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                component_name=comp.component_name,
                component_type=comp.component_type,
                code=comp.code,
                metadata_json=comp.metadata_json,
                created_at=datetime.utcnow(),
            ))

        # 3. Forms
        for fm in payload.forms:
            self.db.add(FrontendForm(
                form_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                form_name=fm.form_name,
                fields_schema=fm.fields_schema,
                validation_schema=fm.validation_schema,
                code=fm.code,
                created_at=datetime.utcnow(),
            ))

        # 4. Hooks
        for hk in payload.hooks:
            self.db.add(FrontendHook(
                hook_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                hook_name=hk.hook_name,
                hook_type=hk.hook_type,
                code=hk.code,
                created_at=datetime.utcnow(),
            ))

        # 5. Test reports
        for test in payload.test_reports:
            self.db.add(FrontendTestReport(
                test_report_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                test_type=test.test_type,
                test_name=test.test_name,
                test_code=test.test_code,
                status="GENERATED",
                created_at=datetime.utcnow(),
            ))

        # 6. UI design artifacts
        for art in payload.ui_design_artifacts:
            self.db.add(UiDesignArtifact(
                artifact_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                artifact_name=art.artifact_name,
                artifact_type=art.artifact_type,
                content=art.content,
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event → orchestrator resumes workflow
        self._publish_event(
            "frontend.generation.completed",
            {
                "event_type": "frontend.generation.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"FrontendGeneration persisted: generation_id={gen.generation_id} "
            f"pages={len(payload.pages)} components={len(payload.components)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the generation as SUPERSEDED and republish frontend.generation.requested
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "frontend.generation.requested",
            {
                "event_type": "frontend.generation.requested",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Frontend regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[FrontendGeneration]:
        return await self.generation_repo.get(generation_id)

    async def get_full_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[FrontendGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[FrontendGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_pages(
        self, generation_id: uuid.UUID
    ) -> List[FrontendPage]:
        return await self.page_repo.list_by_generation(generation_id)

    async def list_components(
        self, generation_id: uuid.UUID
    ) -> List[FrontendComponent]:
        return await self.component_repo.list_by_generation(generation_id)

    async def list_forms(
        self, generation_id: uuid.UUID
    ) -> List[FrontendForm]:
        return await self.form_repo.list_by_generation(generation_id)

    async def list_hooks(
        self, generation_id: uuid.UUID
    ) -> List[FrontendHook]:
        return await self.hook_repo.list_by_generation(generation_id)

    async def list_tests(
        self,
        generation_id: uuid.UUID,
        *,
        test_type: Optional[str] = None,
    ) -> List[FrontendTestReport]:
        return await self.test_repo.list_by_generation(
            generation_id, test_type=test_type
        )

    async def list_ui_design_artifacts(
        self, generation_id: uuid.UUID
    ) -> List[UiDesignArtifact]:
        return await self.ui_design_artifact_repo.list_by_generation(generation_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
