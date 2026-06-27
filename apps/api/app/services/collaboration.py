"""
CollaborationService – orchestrates database persistence and Kafka dispatching
for Multi-Agent Collaboration Engine transactions (Milestone 14).
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentCollaborationSession,
    AgentConversation,
    AgentMessage,
    AgentReview,
    AgentVote,
    AgentConflict,
    AgentResolution,
)
from app.repositories.collaboration import (
    AgentCollaborationSessionRepository,
    AgentConversationRepository,
    AgentMessageRepository,
    AgentReviewRepository,
    AgentVoteRepository,
    AgentConflictRepository,
    AgentResolutionRepository,
)

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

logger = logging.getLogger("api-gateway.collaboration-service")


class CollaborationService:
    """
    Orchestrates collaboration sessions, messages, votes, reviews, and conflicts.
    """

    def __init__(
        self,
        session_repo: AgentCollaborationSessionRepository,
        conversation_repo: AgentConversationRepository,
        message_repo: AgentMessageRepository,
        review_repo: AgentReviewRepository,
        vote_repo: AgentVoteRepository,
        conflict_repo: AgentConflictRepository,
        resolution_repo: AgentResolutionRepository,
        db: AsyncSession,
    ):
        self.session_repo = session_repo
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.review_repo = review_repo
        self.vote_repo = vote_repo
        self.conflict_repo = conflict_repo
        self.resolution_repo = resolution_repo
        self.db = db

        self._event_pub = None
        from app.config import settings as _svc_settings
        if _kafka_available and not _svc_settings.KAFKA_DISABLED:
            try:
                self._event_pub = KafkaEventPublisher()
            except Exception as exc:
                logger.warning(f"Kafka publisher unavailable: {exc}")

    # ── Write workflows ───────────────────────────────────────────────────────

    async def start_session(
        self, project_id: uuid.UUID, workflow_id: uuid.UUID
    ) -> AgentCollaborationSession:
        """
        Initializes an active agent collaboration session.
        """
        session = AgentCollaborationSession(
            session_id=uuid.uuid4(),
            project_id=project_id,
            workflow_id=workflow_id,
            status="ACTIVE",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(session)
        await self.db.flush()

        # Automatically start a general channel conversation
        conversation = AgentConversation(
            conversation_id=uuid.uuid4(),
            session_id=session.session_id,
            title="General Collaboration Channel",
            created_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Collaboration session started: session_id={session.session_id}")
        return session

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        sender_agent: str,
        recipient_agent: Optional[str],
        content: str,
        message_metadata: Optional[dict] = None,
    ) -> AgentMessage:
        """
        Persists a communication message and dispatches event.
        """
        message = AgentMessage(
            message_id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_agent=sender_agent,
            recipient_agent=recipient_agent,
            content=content,
            message_metadata=message_metadata,
            created_at=datetime.utcnow(),
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        self._publish_event(
            "agent.message.sent",
            {
                "event_type": "agent.message.sent",
                "message_id": str(message.message_id),
                "conversation_id": str(conversation_id),
                "sender_agent": sender_agent,
                "recipient_agent": recipient_agent,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return message

    async def request_review(
        self,
        session_id: uuid.UUID,
        reviewer_agent: str,
        target_agent: str,
        artifact_type: str,
        artifact_id: uuid.UUID,
        comments: Optional[str] = None,
    ) -> AgentReview:
        """
        Creates a pending peer-review request.
        """
        review = AgentReview(
            review_id=uuid.uuid4(),
            session_id=session_id,
            reviewer_agent=reviewer_agent,
            target_agent=target_agent,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            status="PENDING",
            comments=comments,
            created_at=datetime.utcnow(),
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)

        self._publish_event(
            "agent.review.requested",
            {
                "event_type": "agent.review.requested",
                "review_id": str(review.review_id),
                "session_id": str(session_id),
                "reviewer_agent": reviewer_agent,
                "target_agent": target_agent,
                "artifact_type": artifact_type,
                "artifact_id": str(artifact_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return review

    async def complete_review(
        self,
        review_id: uuid.UUID,
        status: str,
        comments: Optional[str] = None,
    ) -> AgentReview:
        """
        Closes a review request with decisions and triggers completed event.
        """
        review = await self.review_repo.get(review_id)
        if not review:
            raise ValueError(f"AgentReview '{review_id}' not found")

        review.status = status
        if comments:
            review.comments = comments
        await self.db.commit()
        await self.db.refresh(review)

        self._publish_event(
            "agent.review.completed",
            {
                "event_type": "agent.review.completed",
                "review_id": str(review.review_id),
                "session_id": str(review.session_id),
                "reviewer_agent": review.reviewer_agent,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return review

    async def start_vote(
        self, session_id: uuid.UUID, topic: str, voter_agents: List[str]
    ) -> None:
        """
        Dispatches starting consensus vote event.
        """
        self._publish_event(
            "agent.vote.started",
            {
                "event_type": "agent.vote.started",
                "session_id": str(session_id),
                "topic": topic,
                "voters": voter_agents,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def cast_vote(
        self,
        session_id: uuid.UUID,
        topic: str,
        voter_agent: str,
        decision: str,
    ) -> AgentVote:
        """
        Logs an individual vote choice.
        """
        vote = AgentVote(
            vote_id=uuid.uuid4(),
            session_id=session_id,
            topic=topic,
            voter_agent=voter_agent,
            decision=decision,
            voted_at=datetime.utcnow(),
        )
        self.db.add(vote)
        await self.db.commit()
        await self.db.refresh(vote)

        self._publish_event(
            "agent.vote.completed",
            {
                "event_type": "agent.vote.completed",
                "vote_id": str(vote.vote_id),
                "session_id": str(session_id),
                "topic": topic,
                "voter_agent": voter_agent,
                "decision": decision,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return vote

    async def create_conflict(
        self,
        session_id: uuid.UUID,
        title: str,
        description: str,
        severity: str,
    ) -> AgentConflict:
        """
        Logs a newly escalated agent execution conflict.
        """
        conflict = AgentConflict(
            conflict_id=uuid.uuid4(),
            session_id=session_id,
            title=title,
            description=description,
            severity=severity,
            status="OPEN",
            created_at=datetime.utcnow(),
        )
        self.db.add(conflict)
        await self.db.commit()
        await self.db.refresh(conflict)

        self._publish_event(
            "agent.conflict.created",
            {
                "event_type": "agent.conflict.created",
                "conflict_id": str(conflict.conflict_id),
                "session_id": str(session_id),
                "title": title,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return conflict

    async def resolve_conflict(
        self,
        conflict_id: uuid.UUID,
        resolved_by: str,
        resolution_strategy: str,
        details: str,
    ) -> AgentConflict:
        """
        Documents decision details and updates conflict status.
        """
        conflict = await self.conflict_repo.get(conflict_id)
        if not conflict:
            raise ValueError(f"AgentConflict '{conflict_id}' not found")

        conflict.status = "RESOLVED"
        resolution = AgentResolution(
            resolution_id=uuid.uuid4(),
            conflict_id=conflict_id,
            resolved_by=resolved_by,
            resolution_strategy=resolution_strategy,
            details=details,
            resolved_at=datetime.utcnow(),
        )
        self.db.add(resolution)
        await self.db.commit()
        await self.db.refresh(conflict)

        self._publish_event(
            "agent.conflict.resolved",
            {
                "event_type": "agent.conflict.resolved",
                "conflict_id": str(conflict_id),
                "session_id": str(conflict.session_id),
                "resolved_by": resolved_by,
                "strategy": resolution_strategy,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return conflict

    async def complete_session(self, session_id: uuid.UUID) -> AgentCollaborationSession:
        """
        Updates session status to COMPLETED and alerts orchestrator.
        """
        session = await self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"AgentCollaborationSession '{session_id}' not found")

        session.status = "COMPLETED"
        await self.db.commit()
        await self.db.refresh(session)

        self._publish_event(
            "agent.collaboration.completed",
            {
                "event_type": "agent.collaboration.completed",
                "session_id": str(session_id),
                "workflow_id": str(session.workflow_id),
                "project_id": str(session.project_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        return session

    # ── Read workflows ────────────────────────────────────────────────────────

    async def get_session(self, session_id: uuid.UUID) -> Optional[AgentCollaborationSession]:
        return await self.session_repo.get(session_id)

    async def get_full_session(self, session_id: uuid.UUID) -> Optional[AgentCollaborationSession]:
        # Simple eager loading logic simulated by returning model instance
        return await self.session_repo.get(session_id)

    async def get_message(self, message_id: uuid.UUID) -> Optional[AgentMessage]:
        return await self.message_repo.get(message_id)

    async def get_review(self, review_id: uuid.UUID) -> Optional[AgentReview]:
        return await self.review_repo.get(review_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self._event_pub:
            try:
                self._event_pub.publish(topic, payload)
            except Exception as exc:
                logger.warning(f"Kafka publish failed [{topic}]: {exc}")
        else:
            logger.debug(f"[Kafka stub] Event skipped: {topic}")
