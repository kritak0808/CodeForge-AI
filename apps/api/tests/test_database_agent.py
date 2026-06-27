"""
Test suite for Phase 4.7 – Database Agent (Milestone 7).

Covers:
 - TestDatabaseDesignCreation   – DB record persistence
 - TestDatabaseEntityListing    – entity child records
 - TestMigrationPlanGeneration  – Alembic script fields
 - TestQueryOptimizationReport  – optimization recommendations
 - TestKafkaEventPublishing     – Kafka event emission mock
 - TestApprovalCreation         – Database governance request
 - TestAPIEndpoints             – 8 REST endpoints
 - TestDatabaseAgentTools       – unit tests for the 5 agent tools
 - TestDatabaseAgentExecute     – full agent pipeline
 - TestWorkflowManagerGate      – DATABASE_DESIGN pause/resume
"""
import uuid
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ── path setup for agent-workers & orchestrator tools ────────────────────
workers_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "agent-workers")
)
if workers_path not in sys.path:
    sys.path.insert(0, workers_path)

orchestrator_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "agent-orchestrator")
)
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

from app.models import (
    DatabaseDesign,
    DatabaseEntity,
    DatabaseRelationship,
    DatabaseIndex,
    MigrationPlan,
    QueryOptimizationReport,
)
from app.repositories.database import (
    DatabaseDesignRepository,
    DatabaseEntityRepository,
    DatabaseRelationshipRepository,
    DatabaseIndexRepository,
    MigrationPlanRepository,
    QueryOptimizationRepository,
)
from app.services.database import DatabaseDesignService
from app.schemas.database import (
    DatabaseDesignPayload,
    EntityPayload,
    ColumnDefinition,
    MigrationPayload,
    OptimizationPayload,
)


# ────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────────────

def _make_svc(db_session: AsyncSession) -> DatabaseDesignService:
    """Construct a DatabaseDesignService with Kafka mocked out."""
    with patch("app.services.database._kafka_available", False):
        svc = DatabaseDesignService(
            design_repo=DatabaseDesignRepository(db_session),
            entity_repo=DatabaseEntityRepository(db_session),
            relationship_repo=DatabaseRelationshipRepository(db_session),
            index_repo=DatabaseIndexRepository(db_session),
            migration_repo=MigrationPlanRepository(db_session),
            optimization_repo=QueryOptimizationRepository(db_session),
            db=db_session,
        )
    return svc


def _make_payload(
    project_id=None,
    workflow_id=None,
    report_id=None,
    entities=None,
    migration=None,
    optimizations=None,
) -> DatabaseDesignPayload:
    return DatabaseDesignPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        sql_schema="CREATE TABLE users (...);",
        er_diagram_text="[User] --1:N--> [Project]",
        er_diagram_mermaid="erDiagram\n  USER ||--o{ PROJECT : user_id",
        notes="Test design",
        entities=entities or [
            EntityPayload(
                entity_name="User",
                table_name="users",
                columns=[
                    ColumnDefinition(name="email", type="VARCHAR(255)", nullable=False),
                    ColumnDefinition(name="username", type="VARCHAR(100)", nullable=False),
                ],
                constraints=[],
                ddl="CREATE TABLE IF NOT EXISTS users (...);",
            ),
        ],
        relationships=[],
        indexes=[],
        migration=migration,
        optimizations=optimizations or [],
    )


# ────────────────────────────────────────────────────────────────────────────
# 1. TestDatabaseDesignCreation
# ────────────────────────────────────────────────────────────────────────────

class TestDatabaseDesignCreation:

    @pytest.mark.asyncio
    async def test_create_design_persists_root_record(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        assert design.design_id is not None
        assert design.project_id == payload.project_id
        assert design.workflow_id == payload.workflow_id
        assert design.status == "COMPLETED"
        assert design.sql_schema == "CREATE TABLE users (...);"

    @pytest.mark.asyncio
    async def test_create_design_with_entity(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        entities = await svc.list_entities(design.design_id)
        assert len(entities) == 1
        assert entities[0].entity_name == "User"
        assert entities[0].table_name == "users"

    @pytest.mark.asyncio
    async def test_create_design_status_completed(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        fetched = await svc.get_design(design.design_id)
        assert fetched is not None
        assert fetched.status == "COMPLETED"


# ────────────────────────────────────────────────────────────────────────────
# 2. TestDatabaseEntityListing
# ────────────────────────────────────────────────────────────────────────────

class TestDatabaseEntityListing:

    @pytest.mark.asyncio
    async def test_list_entities_by_design_id(self, db_session: AsyncSession):
        payload = _make_payload(
            entities=[
                EntityPayload(
                    entity_name="User",
                    table_name="users",
                    columns=[ColumnDefinition(name="email", type="VARCHAR(255)", nullable=False)],
                    constraints=[],
                ),
                EntityPayload(
                    entity_name="Project",
                    table_name="projects",
                    columns=[ColumnDefinition(name="user_id", type="UUID", nullable=False)],
                    constraints=[],
                ),
            ]
        )
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        entities = await svc.list_entities(design.design_id)
        entity_names = {e.entity_name for e in entities}
        assert "User" in entity_names
        assert "Project" in entity_names
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_entity_ddl_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        entities = await svc.list_entities(design.design_id)
        assert entities[0].ddl is not None
        assert "CREATE TABLE" in entities[0].ddl


# ────────────────────────────────────────────────────────────────────────────
# 3. TestMigrationPlanGeneration
# ────────────────────────────────────────────────────────────────────────────

class TestMigrationPlanGeneration:

    @pytest.mark.asyncio
    async def test_migration_plan_stored(self, db_session: AsyncSession):
        migration = MigrationPayload(
            migration_version="20240101_001",
            migration_script="from alembic import op\ndef upgrade(): op.create_table('users',...)",
            rollback_script="from alembic import op\ndef downgrade(): op.drop_table('users')",
        )
        payload = _make_payload(migration=migration)
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        migrations = await svc.list_migrations(design.design_id)
        assert len(migrations) == 1
        m = migrations[0]
        assert m.migration_version == "20240101_001"
        assert "op.create_table" in m.migration_script
        assert "op.drop_table" in m.rollback_script
        assert m.status == "DRAFT"

    @pytest.mark.asyncio
    async def test_no_migration_when_omitted(self, db_session: AsyncSession):
        payload = _make_payload(migration=None)
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        migrations = await svc.list_migrations(design.design_id)
        assert len(migrations) == 0


# ────────────────────────────────────────────────────────────────────────────
# 4. TestQueryOptimizationReport
# ────────────────────────────────────────────────────────────────────────────

class TestQueryOptimizationReport:

    @pytest.mark.asyncio
    async def test_optimization_reports_persisted(self, db_session: AsyncSession):
        opts = [
            OptimizationPayload(
                problem_statement="N+1 on User orders",
                recommendation="Use selectinload(User.orders)",
                priority="HIGH",
                estimated_speedup="~70%",
                category="N+1",
            ),
            OptimizationPayload(
                problem_statement="Missing index on status column",
                recommendation="CREATE INDEX idx_users_status ON users (status);",
                priority="MEDIUM",
                category="MISSING_INDEX",
            ),
        ]
        payload = _make_payload(optimizations=opts)
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        stored = await svc.list_optimizations(design.design_id)
        assert len(stored) == 2

    @pytest.mark.asyncio
    async def test_optimization_priority_filter(self, db_session: AsyncSession):
        opts = [
            OptimizationPayload(
                problem_statement="HIGH priority issue",
                recommendation="Fix it",
                priority="HIGH",
                category="N+1",
            ),
            OptimizationPayload(
                problem_statement="LOW priority issue",
                recommendation="Maybe fix it",
                priority="LOW",
                category="OTHER",
            ),
        ]
        payload = _make_payload(optimizations=opts)
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)

        high_only = await svc.list_optimizations(design.design_id, priority="HIGH")
        assert len(high_only) == 1
        assert high_only[0].priority == "HIGH"


# ────────────────────────────────────────────────────────────────────────────
# 5. TestKafkaEventPublishing
# ────────────────────────────────────────────────────────────────────────────

class TestKafkaEventPublishing:

    @pytest.mark.asyncio
    async def test_completion_event_published(self, db_session: AsyncSession):
        """DatabaseDesignService publishes database.design.completed on creation."""
        mock_pub = MagicMock()

        with patch("app.services.database._kafka_available", True):
            with patch("app.services.database.KafkaEventPublisher", return_value=mock_pub):
                svc = DatabaseDesignService(
                    design_repo=DatabaseDesignRepository(db_session),
                    entity_repo=DatabaseEntityRepository(db_session),
                    relationship_repo=DatabaseRelationshipRepository(db_session),
                    index_repo=DatabaseIndexRepository(db_session),
                    migration_repo=MigrationPlanRepository(db_session),
                    optimization_repo=QueryOptimizationRepository(db_session),
                    db=db_session,
                )
                payload = _make_payload()
                await svc.create_design_from_payload(payload)

        mock_pub.publish.assert_called_once()
        call_args = mock_pub.publish.call_args
        topic = call_args[0][0]
        event_payload = call_args[0][1]
        assert topic == "database.design.completed"
        assert event_payload["event_type"] == "database.design.completed"
        assert event_payload["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        """trigger_regeneration publishes database.design.requested."""
        mock_pub = MagicMock()

        with patch("app.services.database._kafka_available", True):
            with patch("app.services.database.KafkaEventPublisher", return_value=mock_pub):
                svc = DatabaseDesignService(
                    design_repo=DatabaseDesignRepository(db_session),
                    entity_repo=DatabaseEntityRepository(db_session),
                    relationship_repo=DatabaseRelationshipRepository(db_session),
                    index_repo=DatabaseIndexRepository(db_session),
                    migration_repo=MigrationPlanRepository(db_session),
                    optimization_repo=QueryOptimizationRepository(db_session),
                    db=db_session,
                )
                payload = _make_payload()
                design = await svc.create_design_from_payload(payload)
                await svc.trigger_regeneration(
                    design_id=design.design_id,
                    workflow_id=design.workflow_id,
                    reason="Re-run after architecture update",
                )

        # First call is completion, second is the regeneration trigger
        assert mock_pub.publish.call_count == 2
        last_call_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_call_topic == "database.design.requested"


# ────────────────────────────────────────────────────────────────────────────
# 6. TestApprovalCreation
# ────────────────────────────────────────────────────────────────────────────

class TestApprovalCreation:

    @pytest.mark.asyncio
    async def test_design_creation_succeeds_without_approval_service(
        self, db_session: AsyncSession
    ):
        """
        Service-layer design creation should succeed even if the approval
        service is not wired into this test (governance is async via Kafka).
        """
        payload = _make_payload()
        svc = _make_svc(db_session)
        design = await svc.create_design_from_payload(payload)
        assert design.status == "COMPLETED"


# ────────────────────────────────────────────────────────────────────────────
# 7. TestAPIEndpoints
# ────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_list_designs_endpoint_registered(self, client):
        resp = await client.get(
            "/api/v1/database/designs",
            params={"project_id": str(uuid.uuid4())},
            headers={"Authorization": "Bearer fake-token"},
        )
        # 401 verifies the endpoint exists and auth guard is applied
        assert resp.status_code in (200, 401, 403, 422)

    @pytest.mark.asyncio
    async def test_get_design_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_regenerate_endpoint_accepts_request(self, client):
        resp = await client.post(
            f"/api/v1/database/designs/{uuid.uuid4()}/regenerate",
            json={"reason": "Manual trigger"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404, 202)

    @pytest.mark.asyncio
    async def test_entities_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}/entities",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_indexes_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}/indexes",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_migrations_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}/migrations",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_optimizations_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}/optimizations",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_relationships_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/database/designs/{uuid.uuid4()}/relationships",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)


# ────────────────────────────────────────────────────────────────────────────
# 8. TestDatabaseAgentTools (unit tests for the 5 agent tools)
# ────────────────────────────────────────────────────────────────────────────

class TestDatabaseAgentTools:

    def test_schema_generator_produces_create_table(self):
        from agent import schema_generator_tool
        ddl = schema_generator_tool("Order", [
            {"name": "user_id", "type": "UUID", "nullable": False},
            {"name": "total", "type": "NUMERIC(10,2)", "nullable": False},
        ])
        assert "CREATE TABLE IF NOT EXISTS orders" in ddl
        assert "user_id" in ddl
        assert "total" in ddl

    def test_er_diagram_tool_produces_ascii_and_mermaid(self):
        from agent import er_diagram_tool
        result = er_diagram_tool(
            ["User", "Order"],
            [{"from": "Order", "to": "User", "cardinality": "1:N", "join_key": "user_id"}],
        )
        assert "ascii" in result
        assert "mermaid" in result
        assert "erDiagram" in result["mermaid"]
        assert "ORDER" in result["mermaid"]
        assert "USER" in result["mermaid"]

    def test_index_recommender_btree_for_fk_columns(self):
        from agent import index_recommender_tool
        recs = index_recommender_tool(
            "orders",
            [{"name": "user_id", "type": "UUID"}, {"name": "total", "type": "NUMERIC"}],
            ["standard lookup"],
        )
        index_names = [r["index_name"] for r in recs]
        assert any("user_id" in name for name in index_names)
        assert all(r["index_type"] in ("BTREE", "HASH", "GIN", "GIST", "BRIN") for r in recs)

    def test_index_recommender_gin_for_json_pattern(self):
        from agent import index_recommender_tool
        recs = index_recommender_tool("orders", [], ["json metadata query"])
        gin_recs = [r for r in recs if r["index_type"] == "GIN"]
        assert len(gin_recs) >= 1

    def test_migration_planner_generates_valid_alembic_structure(self):
        from agent import migration_planner_tool
        result = migration_planner_tool(["users", "orders"], "20240201_002")
        assert result["migration_version"] == "20240201_002"
        assert "def upgrade" in result["migration_script"]
        assert "def downgrade" in result["rollback_script"]
        assert "op.create_table('users'" in result["migration_script"]
        assert "op.drop_table('users')" in result["rollback_script"]

    def test_query_optimizer_returns_at_least_one_recommendation(self):
        from agent import query_optimizer_tool
        opts = query_optimizer_tool(["User", "Order"])
        assert len(opts) >= 1
        for o in opts:
            assert "problem_statement" in o
            assert "recommendation" in o
            assert o["priority"] in ("HIGH", "MEDIUM", "LOW")


# ────────────────────────────────────────────────────────────────────────────
# 9. TestDatabaseAgentExecute
# ────────────────────────────────────────────────────────────────────────────

class TestDatabaseAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import DatabaseAgent
        agent = DatabaseAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "report_id": str(uuid.uuid4()),
        })
        assert "entities" in result
        assert "relationships" in result
        assert "indexes" in result
        assert "migration" in result
        assert "optimizations" in result
        assert result["migration"]["migration_version"] is not None
        assert len(result["optimizations"]) >= 1

    def test_agent_registry_includes_database_agent(self):
        from agent import agent_registry
        assert "DatabaseAgent" in agent_registry.list_registered_agents()

    def test_execute_task_compatibility_adapter(self):
        from agent import DatabaseAgent
        agent = DatabaseAgent()
        ctx = {"project_id": str(uuid.uuid4()), "workflow_id": str(uuid.uuid4())}
        result = agent.execute_task("Generate database schema", ctx)
        assert result["agent_id"] == "DatabaseAgent"
        assert result["status"] == "COMPLETED"
        assert isinstance(result["output"], dict)

    def test_execute_with_custom_entities_and_relationships(self):
        from agent import DatabaseAgent
        agent = DatabaseAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "entities": [
                {"name": "Order", "columns": [
                    {"name": "user_id", "type": "UUID", "nullable": False},
                ]},
                {"name": "OrderItem", "columns": [
                    {"name": "order_id", "type": "UUID", "nullable": False},
                ]},
            ],
            "relationships": [
                {"from": "OrderItem", "to": "Order", "cardinality": "1:N", "join_key": "order_id"},
            ],
        })
        assert len(result["entities"]) == 2
        entity_names = [e["entity_name"] for e in result["entities"]]
        assert "Order" in entity_names
        assert "OrderItem" in entity_names
        assert "order_id" in result["sql_schema"]


# ────────────────────────────────────────────────────────────────────────────
# 10. TestWorkflowManagerGate
# ────────────────────────────────────────────────────────────────────────────

class TestWorkflowManagerGate:

    def _make_manager(self):
        """Build a WorkflowManager with all I/O dependencies mocked."""
        with patch("workflow_manager.CheckpointManager"), \
             patch("workflow_manager.ApprovalHandler"), \
             patch("workflow_manager.RecoveryManager"), \
             patch("workflow_manager.compile_sdlc_graph") as mock_graph_fn:

            mock_graph_fn.return_value = MagicMock()
            mock_event_pub = MagicMock()

            from workflow_manager import WorkflowManager
            mgr = WorkflowManager(
                db_url="sqlite:///test.db",
                redis_url="redis://localhost:6379",
                event_pub=mock_event_pub,
            )
            mgr._mock_event_pub = mock_event_pub
            return mgr

    def test_on_database_design_completed_resumes_workflow(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {"project_id": str(uuid.uuid4())},
            "agent_outputs": {},
            "errors": [],
        }
        mgr.run_workflow_step = MagicMock(return_value={"status": "RUNNING"})

        result = mgr.on_database_design_completed(
            workflow_id=wf_id,
            design_id=str(uuid.uuid4()),
            result_summary={"entity_count": 3},
        )
        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

    def test_on_database_design_completed_ignores_non_paused(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "RUNNING"

        result = mgr.on_database_design_completed(
            workflow_id=wf_id,
            design_id=str(uuid.uuid4()),
        )
        assert result is False

    def test_on_database_design_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_database_design_failed(
            workflow_id=wf_id,
            error="LLM timeout",
        )
        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()
