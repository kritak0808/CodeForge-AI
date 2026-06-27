import uuid
from typing import List, Optional
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.repositories.base import BaseRepository
from app.models import ApprovalPolicy, ApprovalRequest, ApprovalResponse, ApprovalEscalation, ApprovalNotification, ApprovalAuditLog

class ApprovalPolicyRepository(BaseRepository[ApprovalPolicy]):
    def __init__(self, db):
        super().__init__(ApprovalPolicy, db)

    async def get_by_action_type(self, action_type: str) -> Optional[ApprovalPolicy]:
        query = select(ApprovalPolicy).filter(ApprovalPolicy.action_type == action_type)
        result = await self.db.execute(query)
        return result.scalars().first()

class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, db):
        super().__init__(ApprovalRequest, db)

    async def get_pending_requests(self) -> List[ApprovalRequest]:
        query = (
            select(ApprovalRequest)
            .filter(ApprovalRequest.status == "WAITING_FOR_APPROVAL")
            .options(
                selectinload(ApprovalRequest.policy),
                selectinload(ApprovalRequest.responses)
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_request_details(self, approval_id: uuid.UUID) -> Optional[ApprovalRequest]:
        query = (
            select(ApprovalRequest)
            .filter(ApprovalRequest.approval_id == approval_id)
            .options(
                selectinload(ApprovalRequest.policy),
                selectinload(ApprovalRequest.responses),
                selectinload(ApprovalRequest.escalations),
                selectinload(ApprovalRequest.notifications)
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_workflow_active_request(self, workflow_id: uuid.UUID) -> Optional[ApprovalRequest]:
        query = (
            select(ApprovalRequest)
            .filter(
                ApprovalRequest.workflow_id == workflow_id,
                ApprovalRequest.status == "WAITING_FOR_APPROVAL"
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().first()

class ApprovalResponseRepository(BaseRepository[ApprovalResponse]):
    def __init__(self, db):
        super().__init__(ApprovalResponse, db)

class ApprovalEscalationRepository(BaseRepository[ApprovalEscalation]):
    def __init__(self, db):
        super().__init__(ApprovalEscalation, db)

    async def get_untriggered_escalations(self) -> List[ApprovalEscalation]:
        from datetime import datetime
        query = (
            select(ApprovalEscalation)
            .filter(
                ApprovalEscalation.status == "PENDING",
                ApprovalEscalation.scheduled_at <= datetime.utcnow()
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

class ApprovalNotificationRepository(BaseRepository[ApprovalNotification]):
    def __init__(self, db):
        super().__init__(ApprovalNotification, db)

class ApprovalAuditLogRepository(BaseRepository[ApprovalAuditLog]):
    def __init__(self, db):
        super().__init__(ApprovalAuditLog, db)
