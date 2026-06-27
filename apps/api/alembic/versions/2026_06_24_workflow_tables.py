"""add workflow tables

Revision ID: 2026_06_24_workflow
Revises: None
Create Date: 2026-06-24 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_24_workflow'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create agents
    op.create_table(
        'agents',
        sa.Column('agent_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('role_description', sa.String(length=1000), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('agent_id')
    )

    # 2. Create workflows
    op.create_table(
        'workflows',
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('current_state', sa.String(length=50), nullable=False),
        sa.Column('triggered_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('workflow_id')
    )
    op.create_index(op.f('idx_workflows_project'), 'workflows', ['project_id'], unique=False)

    # 3. Create workflow_states
    op.create_table(
        'workflow_states',
        sa.Column('state_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('exited_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('state_id')
    )
    op.create_index(op.f('idx_workflow_states_wf'), 'workflow_states', ['workflow_id'], unique=False)

    # 4. Create tasks
    op.create_table(
        'tasks',
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('depends_on', sa.JSON(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('task_id')
    )
    op.create_index(op.f('idx_tasks_workflow'), 'tasks', ['workflow_id'], unique=False)

    # 5. Create agent_memory
    op.create_table(
        'agent_memory',
        sa.Column('memory_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.String(length=50), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('memory_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.String(length=5000), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('memory_id')
    )
    op.create_index(op.f('idx_agent_memory_lookup'), 'agent_memory', ['agent_id', 'project_id'], unique=False)

    # 6. Create project_memory
    op.create_table(
        'project_memory',
        sa.Column('project_memory_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('val_data', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_memory_id')
    )
    op.create_index(op.f('idx_project_memory_key'), 'project_memory', ['key'], unique=False)

    # 7. Create approvals
    op.create_table(
        'approvals',
        sa.Column('approval_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('approver_id', sa.UUID(), nullable=True),
        sa.Column('approval_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('artifact_payload', sa.JSON(), nullable=False),
        sa.Column('comments', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approver_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('approval_id')
    )
    op.create_index(op.f('idx_approvals_workflow'), 'approvals', ['workflow_id'], unique=False)

    # 8. Create knowledge_sources
    op.create_table(
        'knowledge_sources',
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('tech_tag', sa.String(length=50), nullable=False),
        sa.Column('last_crawled_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('source_id')
    )
    op.create_index(op.f('idx_knowledge_sources_tag'), 'knowledge_sources', ['tech_tag'], unique=False)

    # 9. Create documents
    op.create_table(
        'documents',
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content_path', sa.String(length=500), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.source_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id')
    )

    # 10. Create embeddings
    op.create_table(
        'embeddings',
        sa.Column('embedding_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('vector_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('embedding_id')
    )
    op.create_index(op.f('idx_embeddings_vector_id'), 'embeddings', ['vector_id'], unique=False)

    # 11. Create deployments
    op.create_table(
        'deployments',
        sa.Column('deployment_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('live_url', sa.String(length=500), nullable=True),
        sa.Column('k8s_namespace', sa.String(length=100), nullable=False),
        sa.Column('commit_sha', sa.String(length=40), nullable=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('deployment_id')
    )

    # 12. Create metrics
    op.create_table(
        'metrics',
        sa.Column('metric_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.String(length=50), nullable=False),
        sa.Column('tokens_consumed', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('metric_id')
    )

    # 13. Create notifications
    op.create_table(
        'notifications',
        sa.Column('notification_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.String(length=2000), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('notification_id')
    )


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('metrics')
    op.drop_table('deployments')
    op.drop_table('embeddings')
    op.drop_table('documents')
    op.drop_table('knowledge_sources')
    op.drop_table('approvals')
    op.drop_table('project_memory')
    op.drop_table('agent_memory')
    op.drop_table('tasks')
    op.drop_table('workflow_states')
    op.drop_table('workflows')
    op.drop_table('agents')
