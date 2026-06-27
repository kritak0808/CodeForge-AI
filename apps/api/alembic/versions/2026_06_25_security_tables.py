"""add security tables

Revision ID: 2026_06_25_security
Revises: 2026_06_25_qa
Create Date: 2026-06-25 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_06_25_security'
down_revision = '2026_06_25_qa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create security_generations
    op.create_table(
        'security_generations',
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
    op.create_index(op.f('idx_security_generations_project'), 'security_generations', ['project_id'], unique=False)
    op.create_index(op.f('idx_security_generations_workflow'), 'security_generations', ['workflow_id'], unique=False)

    # 2. Create threat_models
    op.create_table(
        'threat_models',
        sa.Column('model_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('threat_source', sa.String(length=150), nullable=False),
        sa.Column('vulnerability', sa.String(length=500), nullable=False),
        sa.Column('impact', sa.String(length=150), nullable=False),
        sa.Column('risk_level', sa.String(length=50), nullable=False),
        sa.Column('mitigation', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('model_id')
    )
    op.create_index(op.f('idx_threat_models_generation'), 'threat_models', ['generation_id'], unique=False)

    # 3. Create security_findings
    op.create_table(
        'security_findings',
        sa.Column('finding_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('remediation', sa.String(), nullable=True),
        sa.Column('finding_type', sa.String(length=100), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('finding_id')
    )
    op.create_index(op.f('idx_security_findings_generation'), 'security_findings', ['generation_id'], unique=False)

    # 4. Create dependency_scans
    op.create_table(
        'dependency_scans',
        sa.Column('scan_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('package_name', sa.String(length=150), nullable=False),
        sa.Column('installed_version', sa.String(length=50), nullable=False),
        sa.Column('latest_version', sa.String(length=50), nullable=True),
        sa.Column('vulnerabilities_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('scan_id')
    )
    op.create_index(op.f('idx_dependency_scans_generation'), 'dependency_scans', ['generation_id'], unique=False)

    # 5. Create secret_scans
    op.create_table(
        'secret_scans',
        sa.Column('scan_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('secret_type', sa.String(length=100), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('scan_id')
    )
    op.create_index(op.f('idx_secret_scans_generation'), 'secret_scans', ['generation_id'], unique=False)

    # 6. Create rbac_audits
    op.create_table(
        'rbac_audits',
        sa.Column('audit_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('role_name', sa.String(length=100), nullable=False),
        sa.Column('permissions_json', sa.JSON(), nullable=True),
        sa.Column('audit_result', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('audit_id')
    )
    op.create_index(op.f('idx_rbac_audits_generation'), 'rbac_audits', ['generation_id'], unique=False)

    # 7. Create security_reports
    op.create_table(
        'security_reports',
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('generation_id', sa.UUID(), nullable=False),
        sa.Column('report_name', sa.String(length=255), nullable=False),
        sa.Column('overall_risk_score', sa.Float(), nullable=False),
        sa.Column('recommendations_json', sa.JSON(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['security_generations.generation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index(op.f('idx_security_reports_generation'), 'security_reports', ['generation_id'], unique=False)


def downgrade() -> None:
    op.drop_table('security_reports')
    op.drop_table('rbac_audits')
    op.drop_table('secret_scans')
    op.drop_table('dependency_scans')
    op.drop_table('security_findings')
    op.drop_table('threat_models')
    op.drop_table('security_generations')
