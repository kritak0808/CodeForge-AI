"""add collaboration tables

Revision ID: 2026_06_25_collaboration
Revises: 2026_06_25_devops
Create Date: 2026-06-25 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_25_collaboration'
down_revision = '2026_06_25_devops'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create agent_collaboration_sessions
    op.create_table(
        'agent_collaboration_sessions',
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index(op.f('idx_collaboration_sessions_project'), 'agent_collaboration_sessions', ['project_id'], unique=False)
    op.create_index(op.f('idx_collaboration_sessions_workflow'), 'agent_collaboration_sessions', ['workflow_id'], unique=False)

    # 2. Create agent_conversations
    op.create_table(
        'agent_conversations',
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_collaboration_sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('conversation_id')
    )
    op.create_index(op.f('idx_agent_conversations_session'), 'agent_conversations', ['session_id'], unique=False)

    # 3. Create agent_messages
    op.create_table(
        'agent_messages',
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender_agent', sa.String(length=100), nullable=False),
        sa.Column('recipient_agent', sa.String(length=100), nullable=True),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('message_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.conversation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('message_id')
    )
    op.create_index(op.f('idx_agent_messages_conversation'), 'agent_messages', ['conversation_id'], unique=False)

    # 4. Create agent_reviews
    op.create_table(
        'agent_reviews',
        sa.Column('review_id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('reviewer_agent', sa.String(length=100), nullable=False),
        sa.Column('target_agent', sa.String(length=100), nullable=False),
        sa.Column('artifact_type', sa.String(length=100), nullable=False),
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('comments', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_collaboration_sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('review_id')
    )
    op.create_index(op.f('idx_agent_reviews_session'), 'agent_reviews', ['session_id'], unique=False)

    # 5. Create agent_votes
    op.create_table(
        'agent_votes',
        sa.Column('vote_id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('voter_agent', sa.String(length=100), nullable=False),
        sa.Column('decision', sa.String(length=50), nullable=False),
        sa.Column('voted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_collaboration_sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('vote_id')
    )
    op.create_index(op.f('idx_agent_votes_session'), 'agent_votes', ['session_id'], unique=False)

    # 6. Create agent_conflicts
    op.create_table(
        'agent_conflicts',
        sa.Column('conflict_id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['agent_collaboration_sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('conflict_id')
    )
    op.create_index(op.f('idx_agent_conflicts_session'), 'agent_conflicts', ['session_id'], unique=False)

    # 7. Create agent_resolutions
    op.create_table(
        'agent_resolutions',
        sa.Column('resolution_id', sa.UUID(), nullable=False),
        sa.Column('conflict_id', sa.UUID(), nullable=False),
        sa.Column('resolved_by', sa.String(length=100), nullable=False),
        sa.Column('resolution_strategy', sa.String(length=100), nullable=False),
        sa.Column('details', sa.String(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conflict_id'], ['agent_conflicts.conflict_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('resolution_id')
    )
    op.create_index(op.f('idx_agent_resolutions_conflict'), 'agent_resolutions', ['conflict_id'], unique=False)


def downgrade() -> None:
    op.drop_table('agent_resolutions')
    op.drop_table('agent_conflicts')
    op.drop_table('agent_votes')
    op.drop_table('agent_reviews')
    op.drop_table('agent_messages')
    op.drop_table('agent_conversations')
    op.drop_table('agent_collaboration_sessions')
