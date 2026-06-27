"""Create autonomous controller tables – Milestone 17

Revision ID: controller17_001
Revises: cost16_001
Create Date: 2026-06-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "controller17_001"
down_revision = "cost16_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── autonomous_controllers ────────────────────────────────────────────────
    op.create_table(
        "autonomous_controllers",
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
        sa.Column("current_step", sa.String(100), nullable=False),
        sa.Column("budget_limit", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_autonomous_controllers_project_id", "autonomous_controllers", ["project_id"])
    op.create_index("ix_autonomous_controllers_workflow_id", "autonomous_controllers", ["workflow_id"])

    # ── workflow_decisions ────────────────────────────────────────────────────
    op.create_table(
        "workflow_decisions",
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(100), nullable=False),
        sa.Column("decision_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("action_taken", sa.String, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_decisions_controller_id", "workflow_decisions", ["controller_id"])
    op.create_index("ix_workflow_decisions_workflow_id", "workflow_decisions", ["workflow_id"])

    # ── agent_health ──────────────────────────────────────────────────────────
    op.create_table(
        "agent_health",
        sa.Column("health_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="HEALTHY"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_response_time", sa.Float, nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_agent_health_agent_id", "agent_health", ["agent_id"])

    # ── retry_history ─────────────────────────────────────────────────────────
    op.create_table(
        "retry_history",
        sa.Column("retry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(100), nullable=False),
        sa.Column("retry_attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_retry_history_controller_id", "retry_history", ["controller_id"])
    op.create_index("ix_retry_history_workflow_id", "retry_history", ["workflow_id"])

    # ── failure_events ────────────────────────────────────────────────────────
    op.create_table(
        "failure_events",
        sa.Column("failure_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(100), nullable=False),
        sa.Column("error_type", sa.String(150), nullable=False),
        sa.Column("error_message", sa.String, nullable=False),
        sa.Column("severity", sa.String(50), nullable=False, server_default="ERROR"),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_failure_events_controller_id", "failure_events", ["controller_id"])
    op.create_index("ix_failure_events_workflow_id", "failure_events", ["workflow_id"])

    # ── rollback_events ───────────────────────────────────────────────────────
    op.create_table(
        "rollback_events",
        sa.Column("rollback_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_step", sa.String(100), nullable=False),
        sa.Column("target_step", sa.String(100), nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_rollback_events_controller_id", "rollback_events", ["controller_id"])
    op.create_index("ix_rollback_events_workflow_id", "rollback_events", ["workflow_id"])

    # ── execution_plans ───────────────────────────────────────────────────────
    op.create_table(
        "execution_plans",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("steps_json", sa.JSON, nullable=False),
        sa.Column("current_step_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_optimized", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_execution_plans_controller_id", "execution_plans", ["controller_id"])
    op.create_index("ix_execution_plans_workflow_id", "execution_plans", ["workflow_id"])

    # ── controller_logs ───────────────────────────────────────────────────────
    op.create_table(
        "controller_logs",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_controllers.controller_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="INFO"),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_controller_logs_controller_id", "controller_logs", ["controller_id"])
    op.create_index("ix_controller_logs_workflow_id", "controller_logs", ["workflow_id"])


def downgrade() -> None:
    op.drop_table("controller_logs")
    op.drop_table("execution_plans")
    op.drop_table("rollback_events")
    op.drop_table("failure_events")
    op.drop_table("retry_history")
    op.drop_table("agent_health")
    op.drop_table("workflow_decisions")
    op.drop_table("autonomous_controllers")
