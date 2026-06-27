"""add status, tasks_completed, tasks_total to workflows

Revision ID: 2026_06_26_workflow_status
Revises: 2026_06_26_autonomous_controller_tables
Create Date: 2026-06-26 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2026_06_26_workflow_status'
down_revision = '2026_06_26_autonomous_controller_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column (mirrors current_state for frontend consumption)
    op.add_column(
        'workflows',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='CREATED')
    )
    op.create_index('idx_workflows_status', 'workflows', ['status'])

    # Add task progress tracking columns
    op.add_column(
        'workflows',
        sa.Column('tasks_completed', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'workflows',
        sa.Column('tasks_total', sa.Integer(), nullable=False, server_default='0')
    )

    # Back-fill status from current_state for existing rows
    op.execute("""
        UPDATE workflows SET status = CASE
            WHEN current_state = 'COMPLETED' THEN 'COMPLETED'
            WHEN current_state = 'FAILED'    THEN 'FAILED'
            WHEN current_state = 'CANCELLED' THEN 'CANCELLED'
            WHEN current_state = 'PAUSED'    THEN 'PAUSED'
            WHEN current_state = 'INITIATED' THEN 'CREATED'
            ELSE 'RUNNING'
        END
    """)


def downgrade() -> None:
    op.drop_index('idx_workflows_status', table_name='workflows')
    op.drop_column('workflows', 'status')
    op.drop_column('workflows', 'tasks_completed')
    op.drop_column('workflows', 'tasks_total')
