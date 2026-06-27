"""Create observability tables – Milestone 15

Revision ID: obs15_001
Revises:
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "obs15_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── observability_generations ─────────────────────────────────────────────
    op.create_table(
        "observability_generations",
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_obs_gen_project_id", "observability_generations", ["project_id"])
    op.create_index("ix_obs_gen_workflow_id", "observability_generations", ["workflow_id"])

    # ── agent_metrics ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_metrics",
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float, nullable=False, server_default="1"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("extra_metadata", sa.JSON, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_metrics_gen_id", "agent_metrics", ["generation_id"])

    # ── workflow_metrics ──────────────────────────────────────────────────────
    op.create_table(
        "workflow_metrics",
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_name", sa.String(150), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="COMPLETED"),
        sa.Column("throughput_rps", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_metrics_gen_id", "workflow_metrics", ["generation_id"])
    op.create_index("ix_workflow_metrics_wf_id", "workflow_metrics", ["workflow_id"])

    # ── api_metrics ───────────────────────────────────────────────────────────
    op.create_table(
        "api_metrics",
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(300), nullable=False),
        sa.Column("method", sa.String(10), nullable=False, server_default="GET"),
        sa.Column("avg_latency_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column("p99_latency_ms", sa.Float, nullable=True),
        sa.Column("error_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_api_metrics_gen_id", "api_metrics", ["generation_id"])

    # ── system_metrics ────────────────────────────────────────────────────────
    op.create_table(
        "system_metrics",
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_name", sa.String(150), nullable=False),
        sa.Column("cpu_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("memory_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("disk_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_system_metrics_gen_id", "system_metrics", ["generation_id"])

    # ── error_events ──────────────────────────────────────────────────────────
    op.create_table(
        "error_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(150), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="ERROR"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("stack_trace", sa.Text, nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_error_events_gen_id", "error_events", ["generation_id"])

    # ── alert_rules ───────────────────────────────────────────────────────────
    op.create_table(
        "alert_rules",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("metric_name", sa.String(150), nullable=False),
        sa.Column("operator", sa.String(10), nullable=False, server_default="gt"),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_alert_rules_gen_id", "alert_rules", ["generation_id"])

    # ── alert_events ──────────────────────────────────────────────────────────
    op.create_table(
        "alert_events",
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observability_generations.generation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.rule_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("current_value", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_alert_events_gen_id", "alert_events", ["generation_id"])
    op.create_index("ix_alert_events_rule_id", "alert_events", ["rule_id"])


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_table("error_events")
    op.drop_table("system_metrics")
    op.drop_table("api_metrics")
    op.drop_table("workflow_metrics")
    op.drop_table("agent_metrics")
    op.drop_table("observability_generations")
