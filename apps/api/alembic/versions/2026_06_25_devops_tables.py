"""add devops tables

Revision ID: 2026_06_25_devops
Revises: 2026_06_25_security
Create Date: 2026-06-25 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_25_devops'
down_revision = '2026_06_25_security'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create devops_generations
    op.create_table(
        'devops_generations',
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
    op.create_index(op.f('idx_devops_generations_project'), 'devops_generations', ['project_id'], unique=False)
    op.create_index(op.f('idx_devops_generations_workflow'), 'devops_generations', ['workflow_id'], unique=False)

    # 2. Create docker_artifacts
    op.create_table(
        'docker_artifacts',
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index(op.f('idx_docker_artifacts_generation'), 'docker_artifacts', ['generation_id'], unique=False)

    # 3. Create kubernetes_artifacts
    op.create_table(
        'kubernetes_artifacts',
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('manifest_name', sa.String(length=255), nullable=False),
        sa.Column('manifest_type', sa.String(length=100), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index(op.f('idx_kubernetes_artifacts_generation'), 'kubernetes_artifacts', ['generation_id'], unique=False)

    # 4. Create helm_artifacts
    op.create_table(
        'helm_artifacts',
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index(op.f('idx_helm_artifacts_generation'), 'helm_artifacts', ['generation_id'], unique=False)

    # 5. Create terraform_artifacts
    op.create_table(
        'terraform_artifacts',
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index(op.f('idx_terraform_artifacts_generation'), 'terraform_artifacts', ['generation_id'], unique=False)

    # 6. Create cicd_pipelines
    op.create_table(
        'cicd_pipelines',
        sa.Column('pipeline_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('pipeline_id')
    )
    op.create_index(op.f('idx_cicd_pipelines_generation'), 'cicd_pipelines', ['generation_id'], unique=False)

    # 7. Create deployment_templates
    op.create_table(
        'deployment_templates',
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('target_platform', sa.String(length=100), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['devops_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('template_id')
    )
    op.create_index(op.f('idx_deployment_templates_generation'), 'deployment_templates', ['generation_id'], unique=False)


def downgrade() -> None:
    op.drop_table('deployment_templates')
    op.drop_table('cicd_pipelines')
    op.drop_table('terraform_artifacts')
    op.drop_table('helm_artifacts')
    op.drop_table('kubernetes_artifacts')
    op.drop_table('docker_artifacts')
    op.drop_table('devops_generations')
