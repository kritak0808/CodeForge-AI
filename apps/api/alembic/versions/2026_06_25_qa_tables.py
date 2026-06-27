"""add qa tables

Revision ID: 2026_06_25_qa
Revises: 2026_06_25_frontend
Create Date: 2026-06-25 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_25_qa'
down_revision = '2026_06_25_frontend'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create qa_generations
    op.create_table(
        'qa_generations',
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('backend_generation_id', sa.UUID(), nullable=True),
        sa.Column('frontend_generation_id', sa.UUID(), nullable=True),
        sa.Column('design_id', sa.UUID(), nullable=True),
        sa.Column('report_id', sa.UUID(), nullable=True),
        sa.Column('workflow_id', sa.UUID(), nullable=True),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['backend_generation_id'], ['backend_generations.generation_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['frontend_generation_id'], ['frontend_generations.generation_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['design_id'], ['database_designs.design_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['report_id'], ['architecture_reports.report_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('generation_id')
    )
    op.create_index(op.f('idx_qa_generations_project'), 'qa_generations', ['project_id'], unique=False)
    op.create_index(op.f('idx_qa_generations_workflow'), 'qa_generations', ['workflow_id'], unique=False)

    # 2. Create qa_test_suites
    op.create_table(
        'qa_test_suites',
        sa.Column('suite_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('suite_name', sa.String(length=150), nullable=False),
        sa.Column('suite_type', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('suite_id')
    )
    op.create_index(op.f('idx_qa_test_suites_generation'), 'qa_test_suites', ['generation_id'], unique=False)

    # 3. Create qa_test_cases
    op.create_table(
        'qa_test_cases',
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('suite_id', sa.UUID(), nullable=True),
        sa.Column('case_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('test_code', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['suite_id'], ['qa_test_suites.suite_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('case_id')
    )
    op.create_index(op.f('idx_qa_test_cases_generation'), 'qa_test_cases', ['generation_id'], unique=False)

    # 4. Create qa_test_runs
    op.create_table(
        'qa_test_runs',
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('runner_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=True),
        sa.Column('stdout', sa.String(), nullable=True),
        sa.Column('stderr', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('idx_qa_test_runs_generation'), 'qa_test_runs', ['generation_id'], unique=False)

    # 5. Create qa_bug_reports
    op.create_table(
        'qa_bug_reports',
        sa.Column('bug_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('steps_to_reproduce', sa.String(), nullable=True),
        sa.Column('expected_behavior', sa.String(), nullable=True),
        sa.Column('actual_behavior', sa.String(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('bug_id')
    )
    op.create_index(op.f('idx_qa_bug_reports_generation'), 'qa_bug_reports', ['generation_id'], unique=False)

    # 6. Create qa_coverage_reports
    op.create_table(
        'qa_coverage_reports',
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('coverage_type', sa.String(length=50), nullable=False),
        sa.Column('line_coverage', sa.Float(), nullable=False),
        sa.Column('branch_coverage', sa.Float(), nullable=True),
        sa.Column('summary_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index(op.f('idx_qa_coverage_reports_generation'), 'qa_coverage_reports', ['generation_id'], unique=False)

    # 7. Create qa_quality_metrics
    op.create_table(
        'qa_quality_metrics',
        sa.Column('metrics_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('reliability_score', sa.Float(), nullable=True),
        sa.Column('security_score', sa.Float(), nullable=True),
        sa.Column('maintainability_score', sa.Float(), nullable=True),
        sa.Column('details_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['qa_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('metrics_id')
    )
    op.create_index(op.f('idx_qa_quality_metrics_generation'), 'qa_quality_metrics', ['generation_id'], unique=False)


def downgrade() -> None:
    op.drop_table('qa_quality_metrics')
    op.drop_table('qa_coverage_reports')
    op.drop_table('qa_bug_reports')
    op.drop_table('qa_test_runs')
    op.drop_table('qa_test_cases')
    op.drop_table('qa_test_suites')
    op.drop_table('qa_generations')
