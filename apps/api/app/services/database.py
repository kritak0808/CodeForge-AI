"""
DatabaseDesignService – orchestrates persistence of agent-generated
database designs, triggers human governance approval, and republishes
Kafka events for design regeneration.

NOTE: All DB operations use async/await to match the AsyncSession pattern
used throughout the codebase.
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
    DatabaseDesign,
    DatabaseEntity,
    DatabaseRelationship,
    DatabaseIndex,
    MigrationPlan,
    QueryOptimizationReport,
)
from app.repositories.database import (
    DatabaseDesignRepository,
    DatabaseEntityRepository,
    DatabaseRelationshipRepository,
    DatabaseIndexRepository,
    MigrationPlanRepository,
    QueryOptimizationRepository,
)
from app.schemas.database import DatabaseDesignPayload

# ── Kafka Event Publisher ──────────────────────────────────────────────────
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

logger = logging.getLogger("api-gateway.database-service")


class DatabaseDesignService:
    """
    Service layer for the Database Agent.

    Responsibilities:
    - Atomically persist DatabaseDesign and all child records.
    - Fire a Database approval request via the governance engine.
    - Publish Kafka events for workflow orchestration.
    - Expose read helpers for the REST layer.
    """

    def __init__(
        self,
        design_repo: DatabaseDesignRepository,
        entity_repo: DatabaseEntityRepository,
        relationship_repo: DatabaseRelationshipRepository,
        index_repo: DatabaseIndexRepository,
        migration_repo: MigrationPlanRepository,
        optimization_repo: QueryOptimizationRepository,
        db: AsyncSession,
    ):
        self.design_repo = design_repo
        self.entity_repo = entity_repo
        self.relationship_repo = relationship_repo
        self.index_repo = index_repo
        self.migration_repo = migration_repo
        self.optimization_repo = optimization_repo
        self.db = db

        self._event_pub = None
        from app.config import settings as _svc_settings
        if _kafka_available and not _svc_settings.KAFKA_DISABLED:
            try:
                self._event_pub = KafkaEventPublisher()
            except Exception as exc:
                logger.warning(f"Kafka publisher unavailable: {exc}")

    # ── Public: write path ────────────────────────────────────────────────

    async def create_design_from_payload(
        self, payload: DatabaseDesignPayload
    ) -> DatabaseDesign:
        """
        Atomically persist all design artifacts and fire governance approval.
        Called by the Database Agent worker after generation.
        """
        # 1. Root design record
        design = DatabaseDesign(
            design_id=uuid.uuid4(),
            report_id=payload.report_id,
            workflow_id=payload.workflow_id,
            project_id=payload.project_id,
            status="COMPLETED",
            sql_schema=payload.sql_schema,
            er_diagram_text=payload.er_diagram_text,
            er_diagram_mermaid=payload.er_diagram_mermaid,
            notes=payload.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(design)
        await self.db.flush()   # obtain design_id before children

        # 2. Entities
        for ep in payload.entities:
            entity = DatabaseEntity(
                entity_id=uuid.uuid4(),
                design_id=design.design_id,
                entity_name=ep.entity_name,
                table_name=ep.table_name,
                description=ep.description,
                columns=[c.model_dump() for c in ep.columns],
                constraints=[c.model_dump() for c in ep.constraints],
                ddl=ep.ddl,
                created_at=datetime.utcnow(),
            )
            self.db.add(entity)

        # 3. Relationships
        for rp in payload.relationships:
            rel = DatabaseRelationship(
                relationship_id=uuid.uuid4(),
                design_id=design.design_id,
                from_entity=rp.from_entity,
                to_entity=rp.to_entity,
                relationship_type=rp.relationship_type,
                cardinality=rp.cardinality,
                join_key=rp.join_key,
                notes=rp.notes,
                created_at=datetime.utcnow(),
            )
            self.db.add(rel)

        # 4. Indexes
        for ip in payload.indexes:
            idx = DatabaseIndex(
                index_id=uuid.uuid4(),
                design_id=design.design_id,
                table_name=ip.table_name,
                index_name=ip.index_name,
                columns=ip.columns,
                index_type=ip.index_type,
                is_unique=ip.is_unique,
                partial_where=ip.partial_where,
                ddl=ip.ddl,
                rationale=ip.rationale,
                created_at=datetime.utcnow(),
            )
            self.db.add(idx)

        # 5. Migration plan
        if payload.migration:
            mp = MigrationPlan(
                plan_id=uuid.uuid4(),
                design_id=design.design_id,
                migration_version=payload.migration.migration_version,
                migration_script=payload.migration.migration_script,
                rollback_script=payload.migration.rollback_script,
                status="DRAFT",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(mp)

        # 6. Query optimizations
        for op in payload.optimizations:
            opt = QueryOptimizationReport(
                optimization_id=uuid.uuid4(),
                design_id=design.design_id,
                problem_statement=op.problem_statement,
                recommendation=op.recommendation,
                priority=op.priority,
                estimated_speedup=op.estimated_speedup,
                category=op.category,
                created_at=datetime.utcnow(),
            )
            self.db.add(opt)

        await self.db.commit()
        await self.db.refresh(design)

        # 7. Publish completion event → orchestrator resumes workflow
        self._publish_event(
            "database.design.completed",
            {
                "event_type": "database.design.completed",
                "design_id": str(design.design_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            f"DatabaseDesign created: design_id={design.design_id} "
            f"workflow_id={payload.workflow_id}"
        )
        return design

    async def trigger_regeneration(
        self,
        design_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the design as superseded and re-emit database.design.requested
        so the agent worker will regenerate.
        """
        design = await self.design_repo.get(design_id)
        if design:
            design.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "database.design.requested",
            {
                "event_type": "database.design.requested",
                "design_id": str(design_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Regeneration triggered for design_id={design_id}")

    # ── Public: read path ─────────────────────────────────────────────────

    async def get_design(self, design_id: uuid.UUID) -> Optional[DatabaseDesign]:
        return await self.design_repo.get(design_id)

    async def get_full_design(self, design_id: uuid.UUID) -> Optional[DatabaseDesign]:
        """
        Returns the design ORM object; child collections will be lazily
        loaded via SQLAlchemy relationships within the session.
        """
        return await self.design_repo.get(design_id)

    async def list_designs_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DatabaseDesign]:
        return await self.design_repo.list_by_project(project_id, skip=skip, limit=limit)

    async def list_entities(self, design_id: uuid.UUID) -> List[DatabaseEntity]:
        return await self.entity_repo.list_by_design(design_id)

    async def list_relationships(self, design_id: uuid.UUID) -> List[DatabaseRelationship]:
        return await self.relationship_repo.list_by_design(design_id)

    async def list_indexes(self, design_id: uuid.UUID) -> List[DatabaseIndex]:
        return await self.index_repo.list_by_design(design_id)

    async def list_migrations(self, design_id: uuid.UUID) -> List[MigrationPlan]:
        return await self.migration_repo.list_by_design(design_id)

    async def list_optimizations(
        self,
        design_id: uuid.UUID,
        *,
        priority: Optional[str] = None,
    ) -> List[QueryOptimizationReport]:
        return await self.optimization_repo.list_by_design(design_id, priority=priority)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
