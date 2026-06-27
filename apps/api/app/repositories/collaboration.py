"""
Async repositories for the Collaboration Engine (Milestone 14).
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    AgentCollaborationSession,
    AgentConversation,
    AgentMessage,
    AgentReview,
    AgentVote,
    AgentConflict,
    AgentResolution,
)


class AgentCollaborationSessionRepository(BaseRepository[AgentCollaborationSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentCollaborationSession, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[AgentCollaborationSession]:
        stmt = (
            select(AgentCollaborationSession)
            .where(AgentCollaborationSession.project_id == project_id)
            .order_by(AgentCollaborationSession.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[AgentCollaborationSession]:
        stmt = (
            select(AgentCollaborationSession)
            .where(AgentCollaborationSession.workflow_id == workflow_id)
            .order_by(AgentCollaborationSession.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()


class AgentConversationRepository(BaseRepository[AgentConversation]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentConversation, db)

    async def list_by_session(
        self, session_id: uuid.UUID
    ) -> List[AgentConversation]:
        stmt = (
            select(AgentConversation)
            .where(AgentConversation.session_id == session_id)
            .order_by(AgentConversation.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentMessageRepository(BaseRepository[AgentMessage]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentMessage, db)

    async def list_by_conversation(
        self, conversation_id: uuid.UUID
    ) -> List[AgentMessage]:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentReviewRepository(BaseRepository[AgentReview]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentReview, db)

    async def list_by_session(
        self, session_id: uuid.UUID
    ) -> List[AgentReview]:
        stmt = (
            select(AgentReview)
            .where(AgentReview.session_id == session_id)
            .order_by(AgentReview.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentVoteRepository(BaseRepository[AgentVote]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentVote, db)

    async def list_by_session(
        self, session_id: uuid.UUID
    ) -> List[AgentVote]:
        stmt = (
            select(AgentVote)
            .where(AgentVote.session_id == session_id)
            .order_by(AgentVote.voted_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentConflictRepository(BaseRepository[AgentConflict]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentConflict, db)

    async def list_by_session(
        self, session_id: uuid.UUID
    ) -> List[AgentConflict]:
        stmt = (
            select(AgentConflict)
            .where(AgentConflict.session_id == session_id)
            .order_by(AgentConflict.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentResolutionRepository(BaseRepository[AgentResolution]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentResolution, db)

    async def list_by_conflict(
        self, conflict_id: uuid.UUID
    ) -> List[AgentResolution]:
        stmt = (
            select(AgentResolution)
            .where(AgentResolution.conflict_id == conflict_id)
            .order_by(AgentResolution.resolved_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
