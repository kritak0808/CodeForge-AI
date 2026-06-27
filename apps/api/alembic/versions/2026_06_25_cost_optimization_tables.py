"""Create cost optimization tables – Milestone 16

Revision ID: cost16_001
Revises: obs15_001
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "cost16_001"
down_revision = "obs15_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cost_generations ──────────────────────────────────────────────────────
    op.create_table(
        "cost_generations",
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("total_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("estimated_monthly_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cost_gen_project_id", "cost_generations", ["project_id"])
    op.create_index("ix_cost_gen_workflow_id", "cost_generations", ["workflow_id"])

    # ── cost_reports ──────────────────────────────────────────────────────────
    op.create_table(
        "cost_reports",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("current_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("projected_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cost_reports_gen_id", "cost_reports", ["generation_id"])

    # ── resource_usage_metrics ────────────────────────────────────────────────
    op.create_table(
        "resource_usage_metrics",
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("utilization_percent", sa.Float, nullable=False, server_default="0"),
        sa.Column("consumption", sa.Float, nullable=False, server_default="0"),
        sa.Column("unit", sa.String(50), nullable=False, server_default="%"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_resource_usage_metrics_gen_id", "resource_usage_metrics", ["generation_id"])

    # ── optimization_recommendations ──────────────────────────────────────────
    op.create_table(
        "optimization_recommendations",
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("impact_level", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("estimated_savings", sa.Float, nullable=False, server_default="0"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_opt_rec_gen_id", "optimization_recommendations", ["generation_id"])

    # ── savings_estimates ─────────────────────────────────────────────────────
    op.create_table(
        "savings_estimates",
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("monthly_savings", sa.Float, nullable=False, server_default="0"),
        sa.Column("annual_savings", sa.Float, nullable=False, server_default="0"),
        sa.Column("confidence_level", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("assumptions", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_savings_estimates_gen_id", "savings_estimates", ["generation_id"])

    # ── budget_policies ───────────────────────────────────────────────────────
    op.create_table(
        "budget_policies",
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_budget", sa.Float, nullable=False),
        sa.Column("alert_threshold", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_budget_policies_project_id", "budget_policies", ["project_id"])

    # ── cost_alerts ───────────────────────────────────────────────────────────
    op.create_table(
        "cost_alerts",
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("budget_policies.policy_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("current_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("budget_limit", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cost_alerts_gen_id", "cost_alerts", ["generation_id"])
    op.create_index("ix_cost_alerts_policy_id", "cost_alerts", ["policy_id"])


def downgrade() -> None:
    op.drop_table("cost_alerts")
    op.drop_table("budget_policies")
    op.drop_table("savings_estimates")
    op.drop_table("optimization_recommendations")
    op.drop_table("resource_usage_metrics")
    op.drop_table("cost_reports")
    op.drop_table("cost_generations")
