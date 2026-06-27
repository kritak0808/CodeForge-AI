"""add frontend tables

Revision ID: 2026_06_25_frontend
Revises: 2026_06_24_workflow
Create Date: 2026-06-25 02:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_25_frontend'
down_revision = '2026_06_24_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create frontend_generations
    op.create_table(
        'frontend_generations',
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('backend_generation_id', sa.UUID(), nullable=True),
        sa.Column('design_id', sa.UUID(), nullable=True),
        sa.Column('report_id', sa.UUID(), nullable=True),
        sa.Column('workflow_id', sa.UUID(), nullable=True),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('framework', sa.String(length=50), nullable=False),
        sa.Column('language', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['backend_generation_id'], ['backend_generations.generation_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['design_id'], ['database_designs.design_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['report_id'], ['architecture_reports.report_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('generation_id')
    )
    op.create_index(op.f('idx_frontend_generations_project'), 'frontend_generations', ['project_id'], unique=False)
    op.create_index(op.f('idx_frontend_generations_workflow'), 'frontend_generations', ['workflow_id'], unique=False)

    # 2. Create frontend_pages
    op.create_table(
        'frontend_pages',
        sa.Column('page_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('page_type', sa.String(length=50), nullable=False),
        sa.Column('route_path', sa.String(length=500), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('page_id')
    )
    op.create_index(op.f('idx_frontend_pages_generation'), 'frontend_pages', ['generation_id'], unique=False)

    # 3. Create frontend_components
    op.create_table(
        'frontend_components',
        sa.Column('component_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('component_name', sa.String(length=150), nullable=False),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('component_id')
    )
    op.create_index(op.f('idx_frontend_components_generation'), 'frontend_components', ['generation_id'], unique=False)

    # 4. Create frontend_forms
    op.create_table(
        'frontend_forms',
        sa.Column('form_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('form_name', sa.String(length=150), nullable=False),
        sa.Column('fields_schema', sa.JSON(), nullable=True),
        sa.Column('validation_schema', sa.String(), nullable=True),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('form_id')
    )
    op.create_index(op.f('idx_frontend_forms_generation'), 'frontend_forms', ['generation_id'], unique=False)

    # 5. Create frontend_hooks
    op.create_table(
        'frontend_hooks',
        sa.Column('hook_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('hook_name', sa.String(length=150), nullable=False),
        sa.Column('hook_type', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('hook_id')
    )
    op.create_index(op.f('idx_frontend_hooks_generation'), 'frontend_hooks', ['generation_id'], unique=False)

    # 6. Create frontend_test_reports
    op.create_table(
        'frontend_test_reports',
        sa.Column('test_report_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('test_type', sa.String(length=50), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('test_code', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('test_report_id')
    )
    op.create_index(op.f('idx_frontend_test_reports_generation'), 'frontend_test_reports', ['generation_id'], unique=False)

    # 7. Create ui_design_artifacts
    op.create_table(
        'ui_design_artifacts',
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('artifact_name', sa.String(length=150), nullable=False),
        sa.Column('artifact_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['frontend_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index(op.f('idx_ui_design_artifacts_generation'), 'ui_design_artifacts', ['generation_id'], unique=False)


def downgrade() -> None:
    op.drop_table('ui_design_artifacts')
    op.drop_table('frontend_test_reports')
    op.drop_table('frontend_hooks')
    op.drop_table('frontend_forms')
    op.drop_table('frontend_components')
    op.drop_table('frontend_pages')
    op.drop_table('frontend_generations')
