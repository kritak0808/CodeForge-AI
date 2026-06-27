"""
DevOpsGenerationService – orchestrates persistence of DevOps Agent artifacts,
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
    DevopsGeneration,
    DockerArtifact,
    KubernetesArtifact,
    HelmArtifact,
    TerraformArtifact,
    CicdPipeline,
    DeploymentTemplate,
)
from app.repositories.devops import (
    DevopsGenerationRepository,
    DockerArtifactRepository,
    KubernetesArtifactRepository,
    HelmArtifactRepository,
    TerraformArtifactRepository,
    CicdPipelineRepository,
    DeploymentTemplateRepository,
)
from app.schemas.devops import DevOpsGenerationPayload

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

logger = logging.getLogger("api-gateway.devops-service")


class DevOpsGenerationService:
    """
    Service layer for the DevOps Agent.
    """

    def __init__(
        self,
        generation_repo: DevopsGenerationRepository,
        docker_repo: DockerArtifactRepository,
        kubernetes_repo: KubernetesArtifactRepository,
        helm_repo: HelmArtifactRepository,
        terraform_repo: TerraformArtifactRepository,
        pipeline_repo: CicdPipelineRepository,
        template_repo: DeploymentTemplateRepository,
        db: AsyncSession,
    ):
        self.generation_repo = generation_repo
        self.docker_repo = docker_repo
        self.kubernetes_repo = kubernetes_repo
        self.helm_repo = helm_repo
        self.terraform_repo = terraform_repo
        self.pipeline_repo = pipeline_repo
        self.template_repo = template_repo
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
    ) -> DevopsGeneration:
        """
        Creates a PENDING DevopsGeneration record and publishes
        devops.generation.requested so the agent worker picks it up.
        """
        gen = DevopsGeneration(
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
            "devops.generation.requested",
            {
                "event_type": "devops.generation.requested",
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
            f"DevOpsGeneration triggered: generation_id={gen.generation_id} "
            f"workflow_id={workflow_id}"
        )
        return gen

    async def create_generation_from_payload(
        self, payload: DevOpsGenerationPayload
    ) -> DevopsGeneration:
        """
        Called by the agent worker after the DevOpsAgent pipeline completes.
        Atomically persists all child DevOps artifact types and fires the
        devops.generation.completed Kafka event.
        """
        gen = DevopsGeneration(
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

        # 1. Docker Artifacts
        for da in payload.docker_artifacts:
            self.db.add(DockerArtifact(
                artifact_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                file_name=da.file_name,
                content=da.content,
                created_at=datetime.utcnow(),
            ))

        # 2. Kubernetes Manifests
        for ka in payload.kubernetes_artifacts:
            self.db.add(KubernetesArtifact(
                artifact_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                manifest_name=ka.manifest_name,
                manifest_type=ka.manifest_type,
                content=ka.content,
                created_at=datetime.utcnow(),
            ))

        # 3. Helm Charts
        for ha in payload.helm_artifacts:
            self.db.add(HelmArtifact(
                artifact_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                file_path=ha.file_path,
                content=ha.content,
                created_at=datetime.utcnow(),
            ))

        # 4. Terraform Configurations
        for ta in payload.terraform_artifacts:
            self.db.add(TerraformArtifact(
                artifact_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                file_path=ta.file_path,
                content=ta.content,
                created_at=datetime.utcnow(),
            ))

        # 5. CI/CD Pipelines
        for cp in payload.cicd_pipelines:
            self.db.add(CicdPipeline(
                pipeline_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                provider=cp.provider,
                content=cp.content,
                created_at=datetime.utcnow(),
            ))

        # 6. Deployment Templates
        for dt in payload.deployment_templates:
            self.db.add(DeploymentTemplate(
                template_id=uuid.uuid4(),
                generation_id=gen.generation_id,
                target_platform=dt.target_platform,
                content=dt.content,
                created_at=datetime.utcnow(),
            ))

        await self.db.commit()
        await self.db.refresh(gen)

        # Publish completion event
        self._publish_event(
            "devops.generation.events",
            {
                "event_type": "devops.generation.completed",
                "generation_id": str(gen.generation_id),
                "workflow_id": str(payload.workflow_id) if payload.workflow_id else None,
                "project_id": str(payload.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(
            f"DevopsGeneration persisted: generation_id={gen.generation_id} "
            f"docker_artifacts={len(payload.docker_artifacts)} k8s_manifests={len(payload.kubernetes_artifacts)}"
        )
        return gen

    async def trigger_regeneration(
        self,
        generation_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark the generation as SUPERSEDED and republish devops.generation.requested
        """
        gen = await self.generation_repo.get(generation_id)
        if gen:
            gen.status = "SUPERSEDED"
            await self.db.commit()

        self._publish_event(
            "devops.generation.requested",
            {
                "event_type": "devops.generation.requested",
                "generation_id": str(generation_id),
                "workflow_id": str(workflow_id) if workflow_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"DevOps regeneration triggered for generation_id={generation_id}")

    # ── Read path ─────────────────────────────────────────────────────────────

    async def get_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[DevopsGeneration]:
        return await self.generation_repo.get(generation_id)

    async def get_full_generation(
        self, generation_id: uuid.UUID
    ) -> Optional[DevopsGeneration]:
        return await self.generation_repo.get(generation_id)

    async def list_generations_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DevopsGeneration]:
        return await self.generation_repo.list_by_project(
            project_id, skip=skip, limit=limit
        )

    async def list_docker_artifacts(
        self, generation_id: uuid.UUID
    ) -> List[DockerArtifact]:
        return await self.docker_repo.list_by_generation(generation_id)

    async def list_kubernetes_artifacts(
        self, generation_id: uuid.UUID
    ) -> List[KubernetesArtifact]:
        return await self.kubernetes_repo.list_by_generation(generation_id)

    async def list_helm_artifacts(
        self, generation_id: uuid.UUID
    ) -> List[HelmArtifact]:
        return await self.helm_repo.list_by_generation(generation_id)

    async def list_terraform_artifacts(
        self, generation_id: uuid.UUID
    ) -> List[TerraformArtifact]:
        return await self.terraform_repo.list_by_generation(generation_id)

    async def list_cicd_pipelines(
        self, generation_id: uuid.UUID
    ) -> List[CicdPipeline]:
        return await self.pipeline_repo.list_by_generation(generation_id)

    async def list_deployment_templates(
        self, generation_id: uuid.UUID
    ) -> List[DeploymentTemplate]:
        return await self.template_repo.list_by_generation(generation_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped (no publisher): {topic}")
