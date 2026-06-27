"""
REST router for the Collaboration Engine – Milestone 14.
Prefix: /collaboration
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_collaboration_service
from app.schemas.token import TokenData
from app.schemas.collaboration import (
    AgentCollaborationSessionRead,
    AgentCollaborationSessionSummary,
    StartCollaborationRequest,
    AgentConversationRead,
    AgentMessageRead,
    SendMessageRequest,
    AgentReviewRead,
    CreateReviewRequest,
    AgentVoteRead,
    CastVoteRequest,
    AgentConflictRead,
    CreateConflictRequest,
    AgentResolutionRead,
    ResolveConflictRequest,
)
from app.services.collaboration import CollaborationService

router = APIRouter(prefix="/collaboration", tags=["Collaboration Engine"])


# ── POST /collaboration/start ────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=AgentCollaborationSessionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new multi-agent collaboration session",
)
async def start_collaboration(
    body: StartCollaborationRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentCollaborationSessionSummary:
    session = await svc.start_session(body.project_id, body.workflow_id)
    return AgentCollaborationSessionSummary.model_validate(session)


# ── POST /collaboration/message ──────────────────────────────────────────────

@router.post(
    "/message",
    response_model=AgentMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message between specialist agents",
)
async def send_message(
    body: SendMessageRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentMessageRead:
    msg = await svc.send_message(
        conversation_id=body.conversation_id,
        sender_agent=body.sender_agent,
        recipient_agent=body.recipient_agent,
        content=body.content,
        message_metadata=body.message_metadata,
    )
    return AgentMessageRead.model_validate(msg)


# ── POST /collaboration/review ───────────────────────────────────────────────

@router.post(
    "/review",
    response_model=AgentReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Request a peer review or complete a peer review",
)
async def handle_review(
    body: CreateReviewRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentReviewRead:
    # If a review already exists for this artifact/reviewer, we complete it; otherwise create new
    # For simplicity of REST API, if artifact_id is passed, we check if it is active,
    # or create a new review request.
    review = await svc.request_review(
        session_id=body.session_id,
        reviewer_agent=body.reviewer_agent,
        target_agent=body.target_agent,
        artifact_type=body.artifact_type,
        artifact_id=body.artifact_id,
        comments=body.comments,
    )
    if body.status in ("APPROVED", "REWORK_REQUESTED"):
        review = await svc.complete_review(
            review_id=review.review_id,
            status=body.status,
            comments=body.comments,
        )
    return AgentReviewRead.model_validate(review)


# ── POST /collaboration/vote ─────────────────────────────────────────────────

@router.post(
    "/vote",
    response_model=AgentVoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cast a vote on a decision topic",
)
async def cast_vote(
    body: CastVoteRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentVoteRead:
    vote = await svc.cast_vote(
        session_id=body.session_id,
        topic=body.topic,
        voter_agent=body.voter_agent,
        decision=body.decision,
    )
    return AgentVoteRead.model_validate(vote)


# ── POST /collaboration/conflict ──────────────────────────────────────────────

@router.post(
    "/conflict",
    response_model=AgentConflictRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log or escalate an agent execution conflict",
)
async def create_conflict(
    body: CreateConflictRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentConflictRead:
    conflict = await svc.create_conflict(
        session_id=body.session_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
    )
    return AgentConflictRead.model_validate(conflict)


# ── POST /collaboration/resolve ──────────────────────────────────────────────

@router.post(
    "/resolve",
    response_model=AgentConflictRead,
    summary="Resolve an agent execution conflict",
)
async def resolve_conflict(
    body: ResolveConflictRequest,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentConflictRead:
    try:
        conflict = await svc.resolve_conflict(
            conflict_id=body.conflict_id,
            resolved_by=body.resolved_by,
            resolution_strategy=body.resolution_strategy,
            details=body.details,
        )
        return AgentConflictRead.model_validate(conflict)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ── GET /collaboration/sessions/{session_id} ───────────────────────────────

@router.get(
    "/sessions/{session_id}",
    response_model=AgentCollaborationSessionRead,
    summary="Get full collaboration session details by ID",
)
async def get_session(
    session_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentCollaborationSessionRead:
    session = await svc.get_full_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AgentCollaborationSession '{session_id}' not found",
        )
    return AgentCollaborationSessionRead.model_validate(session)


# ── GET /collaboration/messages/{message_id} ───────────────────────────────

@router.get(
    "/messages/{message_id}",
    response_model=AgentMessageRead,
    summary="Get communication message details by ID",
)
async def get_message(
    message_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentMessageRead:
    msg = await svc.get_message(message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AgentMessage '{message_id}' not found",
        )
    return AgentMessageRead.model_validate(msg)


# ── GET /collaboration/reviews/{review_id} ─────────────────────────────────

@router.get(
    "/reviews/{review_id}",
    response_model=AgentReviewRead,
    summary="Get peer review details by ID",
)
async def get_review(
    review_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CollaborationService = Depends(get_collaboration_service),
) -> AgentReviewRead:
    review = await svc.get_review(review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AgentReview '{review_id}' not found",
        )
    return AgentReviewRead.model_validate(review)
