"""
QaGenerationService – orchestrates persistence of QA Agent artifacts,
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
    QaGeneration,
    QaTestSuite,
    QaTestCase,
    QaTestRun,
    QaBugReport,
    QaCoverageReport,
    QaQualityMetrics,
)
from app.repositories.qa import (
    QaGenerationRepository,
    QaTestSuiteRepository,
    QaTestCaseRepository,
    QaTestRunRepository,
    QaBugReportRepository,
    QaCoverageReportRepository,
    QaQualityMetricsRepository,
)
from app.schemas.qa import QaGenerationPayload

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

logger = logging.getLogger("api-gateway.qa-service")


class QaGenerationService:
    """
    Service layer for the QA Agent.
    """

    def __init__(
        self,
        generation_repo: QaGenerationRepository,
        suite_repo: QaTestSuiteRepository,
        case_repo: QaTestCaseRepository,
        run_repo: QaTestRunRepository,
        bug_repo: QaBugReportRepository,
        coverage_repo: QaCoverageReportRepository,
        metrics_repo: QaQualityMetricsRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.suite_repo = suite_repo
        self.case_repo = case_repo
        self.run_repo = run_repo
        self.bug_repo = bug_repo
        self.coverage_repo = coverage_repo
        self.metrics_repo = metrics_repo
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
    ) -> QaGeneration:
        """
        Creates a PENDING QaGeneration record and publishes
        qa.generation.requested so the agent worker picks it up.
        """
        gen = QaGeneration(
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
            "qa.generation.requested",
            {
                "event_type": "qa.generation.requested",
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
            f"QaGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: QaGenerationPayload
    ) -> QaGeneration:
        """
        Called by the agent worker after the QAAgent pipeline completes.
        Atomically persists all child QA artifact types and fires the
        qa.generation.completed Kafka event.
        """
        gen = QaGeneration(
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

        # Keep a mapping of suite_name -> suite_id to hook test cases properly
        suite_id_map = {}

        # 1. Test Suites
        for suite in payload.test_suites:
            s_id = uuid.uuid4()
            suite_id_map[suite.suite_name] = s_id
            self.db.add(QaTestSuite(
                suite_id=s_id,
                generation_id=gen.generation_id,
                suite_name=suite.suite_name,
                suite_type=suite.suite_type,
                file_path=suite.file_path,
                code=suite.code,
                created_at=datetime.utcnow(),
            ))

        # 2. Test Cases
        for case in payload.test_cases:
            # Check if there is a matching suite to assign suite_id
            assigned_suite_id = None
            for sname, sid in suite_id_map.items():
                if sname.lower() in case.case_name.lower():
                    assigned_suite_id = sid
                    break
            self.db.add(QaTestCase(
                case_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                suite_id=assigned_suite_id,
                case_name=case.case_name,
                description=case.description,
                test_code=case.test_code,
                created_at=datetime.utcnow(),
            ))

        # 3. Test Runs
        for run in payload.test_runs:
            self.db.add(QaTestRun(
                run_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                runner_name=run.runner_name,
                status=run.status,
                summary_json=run.summary_json,
                stdout=run.stdout,
                stderr=run.stderr,
                created_at=datetime.utcnow(),
            ))

        # 4. Bug Reports
        for bug in payload.bug_reports:
            self.db.add(QaBugReport(
                bug_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                title=bug.title,
                severity=bug.severity,
                description=bug.description,
                steps_to_reproduce=bug.steps_to_reproduce,
                expected_behavior=bug.expected_behavior,
                actual_behavior=bug.actual_behavior,
                metadata_json=bug.metadata_json,
                created_at=datetime.utcnow(),
            ))

        # 5. Coverage Reports
        for report in payload.coverage_reports:
            self.db.add(QaCoverageReport(
                report_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                coverage_type=report.coverage_type,
                line_coverage=report.line_coverage,
                branch_coverage=report.branch_coverage,
                summary_json=report.summary_json,
                created_at=datetime.utcnow(),
            ))

        # 6. Quality Metrics
        for metric in payload.quality_metrics:
            self.db.add(QaQualityMetrics(
                metrics_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                overall_score=metric.overall_score,
                reliability_score=metric.reliability_score,
                security_score=metric.security_score,
                maintainability_score=metric.maintainability_score,
                details_json=metric.details_json,
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event
        self._publish_event(
            "qa.generation.events",
            {
                "event_type": "qa.generation.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "errors": [bug.description for bug in payload.bug_reports if bug.severity in ("CRITICAL", "HIGH")],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"QaGeneration persisted: generation_id={gen.generation_id} "
            f"suites={len(payload.test_suites)} runs={len(payload.test_runs)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the generation as SUPERSEDED and republish qa.generation.requested
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "qa.generation.requested",
            {
                "event_type": "qa.generation.requested",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"QA regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[QaGeneration]:
        return await self.generation_repo.get(generation_id)

    async def get_full_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[QaGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[QaGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_test_suites(
        self, generation_id: uuid.UUID
    ) -> List[QaTestSuite]:
        return await self.suite_repo.list_by_generation(generation_id)

    async def list_test_cases(
        self, generation_id: uuid.UUID
    ) -> List[QaTestCase]:
        return await self.case_repo.list_by_generation(generation_id)

    async def list_test_runs(
        self, generation_id: uuid.UUID
    ) -> List[QaTestRun]:
        return await self.run_repo.list_by_generation(generation_id)

    async def list_bug_reports(
        self, generation_id: uuid.UUID
    ) -> List[QaBugReport]:
        return await self.bug_repo.list_by_generation(generation_id)

    async def list_coverage_reports(
        self, generation_id: uuid.UUID
    ) -> List[QaCoverageReport]:
        return await self.coverage_repo.list_by_generation(generation_id)

    async def list_quality_metrics(
        self, generation_id: uuid.UUID
    ) -> List[QaQualityMetrics]:
        return await self.metrics_repo.list_by_generation(generation_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
