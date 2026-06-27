"""
SecurityGenerationService – orchestrates persistence of Security Agent artifacts,
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
    SecurityGeneration,
    ThreatModel,
    SecurityFinding,
    DependencyScan,
    SecretScan,
    RbacAudit,
    SecurityReport,
)
from app.repositories.security import (
    SecurityGenerationRepository,
    ThreatModelRepository,
    SecurityFindingRepository,
    DependencyScanRepository,
    SecretScanRepository,
    RbacAuditRepository,
    SecurityReportRepository,
)
from app.schemas.security import SecurityGenerationPayload

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

logger = logging.getLogger("api-gateway.security-service")


class SecurityGenerationService:
    """
    Service layer for the Security Agent.
    """

    def __init__(
        self,
        generation_repo: SecurityGenerationRepository,
        threat_model_repo: ThreatModelRepository,
        finding_repo: SecurityFindingRepository,
        dependency_repo: DependencyScanRepository,
        secret_repo: SecretScanRepository,
        rbac_repo: RbacAuditRepository,
        report_repo: SecurityReportRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.threat_model_repo = threat_model_repo
        self.finding_repo = finding_repo
        self.dependency_repo = dependency_repo
        self.secret_repo = secret_repo
        self.rbac_repo = rbac_repo
        self.report_repo = report_repo
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
        frontend_generation_id: Optional[uuid.UUID] = None,
        design_id: Optional[uuid.UUID] = None,
        report_id: Optional[uuid.UUID] = None,
    ) -> SecurityGeneration:
        """
        Creates a PENDING SecurityGeneration record and publishes
        security.generation.requested so the agent worker picks it up.
        """
        gen = SecurityGeneration(
            generation_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            backend_generation_id=backend_generation_id,
            frontend_generation_id=frontend_generation_id,
            design_id=design_id,
            report_id=report_id,
            status="PENDING",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.commit()
        await self.db.refresh(gen)

        self._publish_event(
            "security.generation.requested",
            {
                "event_type": "security.generation.requested",
                "generation_id": str(gen.generation_id),
                "project_id": str(project_id),
                "workflow_id": str(workflow_id),
                "backend_generation_id": str(backend_generation_id) if backend_generation_id else None,
                "frontend_generation_id": str(frontend_generation_id) if frontend_generation_id else None,
                "design_id": str(design_id) if design_id else None,
                "report_id": str(report_id) if report_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"SecurityGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: SecurityGenerationPayload
    ) -> SecurityGeneration:
        """
        Called by the agent worker after the SecurityAgent pipeline completes.
        Atomically persists all child Security artifact types and fires the
        security.generation.completed Kafka event.
        """
        gen = SecurityGeneration(
            generation_id=uuid.uuid4(),
            project_id=payload.project_id,
            workflow_id=payload.workflow_id,
            backend_generation_id=payload.backend_generation_id,
            frontend_generation_id=payload.frontend_generation_id,
            design_id=payload.design_id,
            report_id=payload.report_id,
            status="COMPLETED",
            notes=payload.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(gen)
        await self.db.flush()

        # 1. Threat Models
        for tm in payload.threat_models:
            self.db.add(ThreatModel(
                model_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                threat_source=tm.threat_source,
                vulnerability=tm.vulnerability,
                impact=tm.impact,
                risk_level=tm.risk_level,
                mitigation=tm.mitigation,
                created_at=datetime.utcnow(),
            ))

        # 2. Security Findings
        for sf in payload.security_findings:
            self.db.add(SecurityFinding(
                finding_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                title=sf.title,
                description=sf.description,
                severity=sf.severity,
                remediation=sf.remediation,
                finding_type=sf.finding_type,
                metadata_json=sf.metadata_json,
                created_at=datetime.utcnow(),
            ))

        # 3. Dependency Scans
        for ds in payload.dependency_scans:
            self.db.add(DependencyScan(
                scan_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                package_name=ds.package_name,
                installed_version=ds.installed_version,
                latest_version=ds.latest_version,
                vulnerabilities_json=ds.vulnerabilities_json,
                status=ds.status,
                created_at=datetime.utcnow(),
            ))

        # 4. Secret Scans
        for ss in payload.secret_scans:
            self.db.add(SecretScan(
                scan_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                file_path=ss.file_path,
                secret_type=ss.secret_type,
                line_number=ss.line_number,
                status=ss.status,
                created_at=datetime.utcnow(),
            ))

        # 5. RBAC Audits
        for ra in payload.rbac_audits:
            self.db.add(RbacAudit(
                audit_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                role_name=ra.role_name,
                permissions_json=ra.permissions_json,
                audit_result=ra.audit_result,
                status=ra.status,
                created_at=datetime.utcnow(),
            ))

        # 6. Security Reports
        for sr in payload.security_reports:
            self.db.add(SecurityReport(
                report_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                report_name=sr.report_name,
                overall_risk_score=sr.overall_risk_score,
                recommendations_json=sr.recommendations_json,
                summary=sr.summary,
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event
        self._publish_event(
            "security.generation.events",
            {
                "event_type": "security.generation.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"SecurityGeneration persisted: generation_id={gen.generation_id} "
            f"threat_models={len(payload.threat_models)} findings={len(payload.security_findings)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the generation as SUPERSEDED and republish security.generation.requested
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "security.generation.requested",
            {
                "event_type": "security.generation.requested",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Security regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[SecurityGeneration]:
        return await self.generation_repo.get(generation_id)

    async def get_full_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[SecurityGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SecurityGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_threat_models(
        self, generation_id: uuid.UUID
    ) -> List[ThreatModel]:
        return await self.threat_model_repo.list_by_generation(generation_id)

    async def list_security_findings(
        self, generation_id: uuid.UUID
    ) -> List[SecurityFinding]:
        return await self.finding_repo.list_by_generation(generation_id)

    async def list_dependency_scans(
        self, generation_id: uuid.UUID
    ) -> List[DependencyScan]:
        return await self.dependency_repo.list_by_generation(generation_id)

    async def list_secret_scans(
        self, generation_id: uuid.UUID
    ) -> List[SecretScan]:
        return await self.secret_repo.list_by_generation(generation_id)

    async def list_rbac_audits(
        self, generation_id: uuid.UUID
    ) -> List[RbacAudit]:
        return await self.rbac_repo.list_by_generation(generation_id)

    async def list_security_reports(
        self, generation_id: uuid.UUID
    ) -> List[SecurityReport]:
        return await self.report_repo.list_by_generation(generation_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
