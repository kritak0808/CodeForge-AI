"""
Test suite for Phase 4.8 – Backend Agent (Milestone 8).

Covers:
  - TestBackendGenerationCreation    – root record + all 5 child types persisted
  - TestApiEndpointListing           – endpoint listing + fields verified
  - TestServiceDefinitionListing     – service defs listing
  - TestRepositoryDefinitionListing  – repo defs listing
  - TestBusinessRuleListing          – rules + filter by type
  - TestApiTestReportListing         – test reports + filter by type
  - TestKafkaEventPublishing         – completed + regeneration event mocks
  - TestAPIEndpoints                 – all 8 REST endpoints (auth guard + routing)
  - TestBackendAgentTools            – unit tests for all 6 agent tools
  - TestBackendAgentExecute          – full pipeline + registry checks
  - TestWorkflowManagerGate          – BACKEND_GENERATION pause/resume/fail
"""
import json
import uuid
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ── path setup ────────────────────────────────────────────────────────────────
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
    BackendGeneration,
    ApiEndpoint,
    ServiceDefinition,
    RepositoryDefinition,
    BusinessRule,
    ApiTestReport,
)
from app.repositories.backend import (
    BackendGenerationRepository,
    ApiEndpointRepository,
    ServiceDefinitionRepository,
    RepositoryDefinitionRepository,
    BusinessRuleRepository,
    ApiTestReportRepository,
)
from app.services.backend import BackendGenerationService
from app.schemas.backend import (
    BackendGenerationPayload,
    ApiEndpointPayload,
    ServiceDefinitionPayload,
    RepositoryDefinitionPayload,
    BusinessRulePayload,
    ApiTestReportPayload,
)


# ────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────────────

def _make_svc(db_session: AsyncSession) -> BackendGenerationService:
    with patch("app.services.backend._kafka_available", False):
        svc = BackendGenerationService(
            generation_repo=BackendGenerationRepository(db_session),
            endpoint_repo=ApiEndpointRepository(db_session),
            service_repo=ServiceDefinitionRepository(db_session),
            repository_repo=RepositoryDefinitionRepository(db_session),
            rule_repo=BusinessRuleRepository(db_session),
            test_repo=ApiTestReportRepository(db_session),
            db=db_session,
        )
    return svc


def _make_payload(
    project_id=None,
    workflow_id=None,
    design_id=None,
    report_id=None,
    endpoints=None,
    services=None,
    repositories=None,
    rules=None,
    test_reports=None,
) -> BackendGenerationPayload:
    return BackendGenerationPayload(
        project_id=project_id or uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        design_id=design_id or uuid.uuid4(),
        report_id=report_id or uuid.uuid4(),
        framework="FastAPI",
        language="Python",
        openapi_spec='{"openapi": "3.1.0", "info": {"title": "Test API"}}',
        notes="Test generation",
        endpoints=endpoints or [
            ApiEndpointPayload(
                method="GET",
                path="/api/v1/users",
                summary="List users",
                auth_required=True,
                rate_limited=False,
            ),
            ApiEndpointPayload(
                method="POST",
                path="/api/v1/users",
                summary="Create user",
                request_schema="class UserCreate(BaseModel): name: str",
                response_schema="class UserRead(BaseModel): id: UUID; name: str",
                router_code="@router.post('/')\nasync def create_user(body: UserCreate): ...",
                auth_required=True,
                rate_limited=True,
            ),
        ],
        services=services or [
            ServiceDefinitionPayload(
                service_name="UserService",
                description="Business logic for User entity",
                code="class UserService:\n    def __init__(self, db): self.db = db\n",
                dependencies="UserRepository",
            ),
        ],
        repositories=repositories or [
            RepositoryDefinitionPayload(
                repo_name="UserRepository",
                model_name="User",
                code="class UserRepository:\n    def __init__(self, db): self.db = db\n",
            ),
        ],
        rules=rules or [
            BusinessRulePayload(
                rule_name="UserValidationRule",
                description="Validates User input",
                rule_type="VALIDATION",
                code="def validate_user(data): ...",
            ),
            BusinessRulePayload(
                rule_name="UserAuthorizationRule",
                description="User resource ownership check",
                rule_type="AUTHORIZATION",
                code="def authorize_user(user_id, owner_id): ...",
            ),
        ],
        test_reports=test_reports or [
            ApiTestReportPayload(
                test_type="integration",
                test_name="test_create_user",
                test_code="async def test_create_user(client): ...",
            ),
            ApiTestReportPayload(
                test_type="api",
                test_name="test_list_users",
                test_code="async def test_list_users(client): ...",
            ),
        ],
    )


# ────────────────────────────────────────────────────────────────────────────
# 1. TestBackendGenerationCreation
# ────────────────────────────────────────────────────────────────────────────

class TestBackendGenerationCreation:

    @pytest.mark.asyncio
    async def test_create_generation_persists_root_record(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        assert gen.generation_id is not None
        assert gen.project_id == payload.project_id
        assert gen.workflow_id == payload.workflow_id
        assert gen.status == "COMPLETED"
        assert gen.framework == "FastAPI"
        assert gen.language == "Python"
        assert gen.openapi_spec is not None

    @pytest.mark.asyncio
    async def test_create_generation_persists_all_child_types(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        endpoints = await svc.list_endpoints(gen.generation_id)
        services = await svc.list_services(gen.generation_id)
        repos = await svc.list_repositories(gen.generation_id)
        rules = await svc.list_rules(gen.generation_id)
        tests = await svc.list_tests(gen.generation_id)

        assert len(endpoints) == 2
        assert len(services) == 1
        assert len(repos) == 1
        assert len(rules) == 2
        assert len(tests) == 2

    @pytest.mark.asyncio
    async def test_create_generation_retrievable_by_id(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        fetched = await svc.get_generation(gen.generation_id)
        assert fetched is not None
        assert fetched.generation_id == gen.generation_id
        assert fetched.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_list_generations_for_project(self, db_session: AsyncSession):
        project_id = uuid.uuid4()
        svc = _make_svc(db_session)

        await svc.create_generation_from_payload(_make_payload(project_id=project_id))
        await svc.create_generation_from_payload(_make_payload(project_id=project_id))

        gens = await svc.list_generations_for_project(project_id)
        assert len(gens) == 2
        assert all(g.project_id == project_id for g in gens)

    @pytest.mark.asyncio
    async def test_trigger_generation_creates_pending_record(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        project_id = uuid.uuid4()
        workflow_id = uuid.uuid4()

        gen = await svc.trigger_generation(
            project_id=project_id,
            workflow_id=workflow_id,
            framework="FastAPI",
        )
        assert gen.status == "PENDING"
        assert gen.project_id == project_id
        assert gen.workflow_id == workflow_id


# ────────────────────────────────────────────────────────────────────────────
# 2. TestApiEndpointListing
# ────────────────────────────────────────────────────────────────────────────

class TestApiEndpointListing:

    @pytest.mark.asyncio
    async def test_endpoints_listed_by_generation(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        endpoints = await svc.list_endpoints(gen.generation_id)
        methods = {ep.method for ep in endpoints}
        assert "GET" in methods
        assert "POST" in methods

    @pytest.mark.asyncio
    async def test_endpoint_fields_stored_correctly(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        endpoints = await svc.list_endpoints(gen.generation_id)
        post_ep = next(ep for ep in endpoints if ep.method == "POST")
        assert post_ep.path == "/api/v1/users"
        assert post_ep.auth_required is True
        assert post_ep.rate_limited is True
        assert post_ep.request_schema is not None
        assert "UserCreate" in post_ep.request_schema
        assert post_ep.router_code is not None
        assert "@router.post" in post_ep.router_code


# ────────────────────────────────────────────────────────────────────────────
# 3. TestServiceDefinitionListing
# ────────────────────────────────────────────────────────────────────────────

class TestServiceDefinitionListing:

    @pytest.mark.asyncio
    async def test_service_definitions_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        services = await svc.list_services(gen.generation_id)
        assert len(services) == 1
        assert services[0].service_name == "UserService"
        assert services[0].dependencies == "UserRepository"

    @pytest.mark.asyncio
    async def test_service_code_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        services = await svc.list_services(gen.generation_id)
        assert "UserService" in services[0].code


# ────────────────────────────────────────────────────────────────────────────
# 4. TestRepositoryDefinitionListing
# ────────────────────────────────────────────────────────────────────────────

class TestRepositoryDefinitionListing:

    @pytest.mark.asyncio
    async def test_repository_definitions_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        repos = await svc.list_repositories(gen.generation_id)
        assert len(repos) == 1
        assert repos[0].repo_name == "UserRepository"
        assert repos[0].model_name == "User"

    @pytest.mark.asyncio
    async def test_repository_code_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        repos = await svc.list_repositories(gen.generation_id)
        assert "UserRepository" in repos[0].code


# ────────────────────────────────────────────────────────────────────────────
# 5. TestBusinessRuleListing
# ────────────────────────────────────────────────────────────────────────────

class TestBusinessRuleListing:

    @pytest.mark.asyncio
    async def test_rules_stored_and_listed(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        rules = await svc.list_rules(gen.generation_id)
        rule_types = {r.rule_type for r in rules}
        assert "VALIDATION" in rule_types
        assert "AUTHORIZATION" in rule_types

    @pytest.mark.asyncio
    async def test_rules_filter_by_type(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        validation_rules = await svc.list_rules(gen.generation_id, rule_type="VALIDATION")
        assert len(validation_rules) == 1
        assert validation_rules[0].rule_name == "UserValidationRule"

        auth_rules = await svc.list_rules(gen.generation_id, rule_type="AUTHORIZATION")
        assert len(auth_rules) == 1
        assert auth_rules[0].rule_name == "UserAuthorizationRule"


# ────────────────────────────────────────────────────────────────────────────
# 6. TestApiTestReportListing
# ────────────────────────────────────────────────────────────────────────────

class TestApiTestReportListing:

    @pytest.mark.asyncio
    async def test_test_reports_stored(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        tests = await svc.list_tests(gen.generation_id)
        assert len(tests) == 2
        test_names = {t.test_name for t in tests}
        assert "test_create_user" in test_names
        assert "test_list_users" in test_names

    @pytest.mark.asyncio
    async def test_test_reports_filter_by_type(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        integration_tests = await svc.list_tests(gen.generation_id, test_type="integration")
        assert len(integration_tests) == 1
        assert integration_tests[0].test_name == "test_create_user"

        api_tests = await svc.list_tests(gen.generation_id, test_type="api")
        assert len(api_tests) == 1
        assert api_tests[0].test_name == "test_list_users"

    @pytest.mark.asyncio
    async def test_test_report_status_defaults_to_generated(self, db_session: AsyncSession):
        payload = _make_payload()
        svc = _make_svc(db_session)
        gen = await svc.create_generation_from_payload(payload)

        tests = await svc.list_tests(gen.generation_id)
        assert all(t.status == "GENERATED" for t in tests)


# ────────────────────────────────────────────────────────────────────────────
# 7. TestKafkaEventPublishing
# ────────────────────────────────────────────────────────────────────────────

class TestKafkaEventPublishing:

    @pytest.mark.asyncio
    async def test_completion_event_published_on_create(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.backend._kafka_available", True), \
             patch("app.services.backend.KafkaEventPublisher", return_value=mock_pub):
            svc = BackendGenerationService(
                generation_repo=BackendGenerationRepository(db_session),
                endpoint_repo=ApiEndpointRepository(db_session),
                service_repo=ServiceDefinitionRepository(db_session),
                repository_repo=RepositoryDefinitionRepository(db_session),
                rule_repo=BusinessRuleRepository(db_session),
                test_repo=ApiTestReportRepository(db_session),
                db=db_session,
            )
            payload = _make_payload()
            await svc.create_generation_from_payload(payload)

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        event = mock_pub.publish.call_args[0][1]
        assert topic == "backend.generation.completed"
        assert event["event_type"] == "backend.generation.completed"
        assert event["workflow_id"] == str(payload.workflow_id)

    @pytest.mark.asyncio
    async def test_trigger_generation_publishes_requested_event(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.backend._kafka_available", True), \
             patch("app.services.backend.KafkaEventPublisher", return_value=mock_pub):
            svc = BackendGenerationService(
                generation_repo=BackendGenerationRepository(db_session),
                endpoint_repo=ApiEndpointRepository(db_session),
                service_repo=ServiceDefinitionRepository(db_session),
                repository_repo=RepositoryDefinitionRepository(db_session),
                rule_repo=BusinessRuleRepository(db_session),
                test_repo=ApiTestReportRepository(db_session),
                db=db_session,
            )
            await svc.trigger_generation(
                project_id=uuid.uuid4(),
                workflow_id=uuid.uuid4(),
            )

        mock_pub.publish.assert_called_once()
        topic = mock_pub.publish.call_args[0][0]
        assert topic == "backend.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_event_published(self, db_session: AsyncSession):
        mock_pub = MagicMock()
        with patch("app.services.backend._kafka_available", True), \
             patch("app.services.backend.KafkaEventPublisher", return_value=mock_pub):
            svc = BackendGenerationService(
                generation_repo=BackendGenerationRepository(db_session),
                endpoint_repo=ApiEndpointRepository(db_session),
                service_repo=ServiceDefinitionRepository(db_session),
                repository_repo=RepositoryDefinitionRepository(db_session),
                rule_repo=BusinessRuleRepository(db_session),
                test_repo=ApiTestReportRepository(db_session),
                db=db_session,
            )
            payload = _make_payload()
            gen = await svc.create_generation_from_payload(payload)
            await svc.trigger_regeneration(
                generation_id=gen.generation_id,
                workflow_id=gen.workflow_id,
                reason="Architecture changed",
            )

        # call 1: backend.generation.completed, call 2: backend.generation.requested
        assert mock_pub.publish.call_count == 2
        last_topic = mock_pub.publish.call_args_list[-1][0][0]
        assert last_topic == "backend.generation.requested"

    @pytest.mark.asyncio
    async def test_regeneration_marks_generation_superseded(self, db_session: AsyncSession):
        svc = _make_svc(db_session)
        payload = _make_payload()
        gen = await svc.create_generation_from_payload(payload)

        await svc.trigger_regeneration(
            generation_id=gen.generation_id,
            workflow_id=gen.workflow_id,
        )

        updated = await svc.get_generation(gen.generation_id)
        assert updated.status == "SUPERSEDED"


# ────────────────────────────────────────────────────────────────────────────
# 8. TestAPIEndpoints
# ────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_generate_endpoint_registered(self, client):
        resp = await client.post(
            "/api/v1/backend/generate",
            json={
                "project_id": str(uuid.uuid4()),
                "workflow_id": str(uuid.uuid4()),
            },
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (202, 401, 403, 422)

    @pytest.mark.asyncio
    async def test_list_generations_endpoint_registered(self, client):
        resp = await client.get(
            "/api/v1/backend/generations",
            params={"project_id": str(uuid.uuid4())},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (200, 401, 403, 422)

    @pytest.mark.asyncio
    async def test_get_generation_returns_404_or_auth_error(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_endpoints_sub_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}/endpoints",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_services_sub_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}/services",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_repositories_sub_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}/repositories",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_rules_sub_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}/rules",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_tests_sub_endpoint_registered(self, client):
        resp = await client.get(
            f"/api/v1/backend/generations/{uuid.uuid4()}/tests",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_regenerate_endpoint_accepts_request(self, client):
        resp = await client.post(
            f"/api/v1/backend/generations/{uuid.uuid4()}/regenerate",
            json={"reason": "Architecture updated"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code in (202, 401, 403, 404)


# ────────────────────────────────────────────────────────────────────────────
# 9. TestBackendAgentTools
# ────────────────────────────────────────────────────────────────────────────

class TestBackendAgentTools:

    def test_api_generator_tool_produces_router_code(self):
        from agent import api_generator_tool
        result = api_generator_tool("Order")
        assert result["method"] == "GET/POST/PUT/DELETE"
        assert "/api/v1/orders" in result["path"]
        assert "@router.get" in result["router_code"]
        assert "@router.post" in result["router_code"]
        assert "OrderCreate" in result["request_schema"]
        assert "OrderRead" in result["response_schema"]
        assert result["auth_required"] is True

    def test_api_generator_tool_correct_table_naming(self):
        from agent import api_generator_tool
        result = api_generator_tool("Category")
        assert "/api/v1/categorys" in result["path"]

    def test_service_generator_tool_produces_class_code(self):
        from agent import service_generator_tool
        result = service_generator_tool("Order")
        assert result["service_name"] == "OrderService"
        assert "class OrderService" in result["code"]
        assert "async def list" in result["code"]
        assert "async def get" in result["code"]
        assert "async def create" in result["code"]
        assert "async def update" in result["code"]
        assert "async def delete" in result["code"]
        assert result["dependencies"] == "OrderRepository"

    def test_repository_generator_tool_produces_class_code(self):
        from agent import repository_generator_tool
        result = repository_generator_tool("Order")
        assert result["repo_name"] == "OrderRepository"
        assert result["model_name"] == "Order"
        assert "class OrderRepository" in result["code"]
        assert "async def get" in result["code"]
        assert "async def create" in result["code"]
        assert "async def delete" in result["code"]

    def test_crud_generator_tool_produces_five_endpoints(self):
        from agent import crud_generator_tool
        endpoints = crud_generator_tool("Order")
        assert len(endpoints) == 5
        methods = {ep["method"] for ep in endpoints}
        assert methods == {"GET", "POST", "PUT", "DELETE"}
        # POST must be rate_limited
        post_ep = next(ep for ep in endpoints if ep["method"] == "POST" and "{order_id}" not in ep["path"])
        assert post_ep["rate_limited"] is True

    def test_test_generator_tool_produces_five_tests(self):
        from agent import backend_test_generator_tool, crud_generator_tool
        crud_eps = crud_generator_tool("Order")
        tests = backend_test_generator_tool("Order", crud_eps)
        assert len(tests) == 5
        test_names = [t["test_name"] for t in tests]
        assert "test_create_order" in test_names
        assert "test_list_orders" in test_names
        assert "test_get_order_not_found" in test_names
        assert "test_update_order" in test_names
        assert "test_delete_order" in test_names

    def test_test_generator_produces_valid_test_code(self):
        from agent import backend_test_generator_tool, crud_generator_tool
        crud_eps = crud_generator_tool("Order")
        tests = backend_test_generator_tool("Order", crud_eps)
        for t in tests:
            assert "@pytest.mark.asyncio" in t["test_code"]
            assert "async def test_" in t["test_code"]

    def test_openapi_generator_tool_produces_valid_json(self):
        from agent import openapi_generator_tool
        spec_str = openapi_generator_tool(["User", "Order"])
        spec = json.loads(spec_str)
        assert spec["openapi"] == "3.1.0"
        assert "/api/v1/users" in spec["paths"]
        assert "/api/v1/orders" in spec["paths"]
        # Check BearerAuth scheme
        schemes = spec["components"]["securitySchemes"]
        assert "BearerAuth" in schemes
        assert schemes["BearerAuth"]["scheme"] == "bearer"

    def test_openapi_generator_includes_crud_paths(self):
        from agent import openapi_generator_tool
        spec_str = openapi_generator_tool(["Product"])
        spec = json.loads(spec_str)
        assert "/api/v1/products" in spec["paths"]
        assert "/api/v1/products/{product_id}" in spec["paths"]
        assert "get" in spec["paths"]["/api/v1/products"]
        assert "post" in spec["paths"]["/api/v1/products"]


# ────────────────────────────────────────────────────────────────────────────
# 10. TestBackendAgentExecute
# ────────────────────────────────────────────────────────────────────────────

class TestBackendAgentExecute:

    def test_execute_returns_complete_payload(self):
        from agent import BackendAgent
        agent = BackendAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        })
        assert "endpoints" in result
        assert "services" in result
        assert "repositories" in result
        assert "rules" in result
        assert "test_reports" in result
        assert "openapi_spec" in result
        assert len(result["endpoints"]) > 0
        assert len(result["services"]) > 0
        assert len(result["repositories"]) > 0

    def test_execute_uses_provided_entities(self):
        from agent import BackendAgent
        agent = BackendAgent()
        result = agent.execute({
            "workflow_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "entities": [{"name": "Order"}, {"name": "Customer"}],
        })
        service_names = [s["service_name"] for s in result["services"]]
        assert "OrderService" in service_names
        assert "CustomerService" in service_names

        repo_names = [r["repo_name"] for r in result["repositories"]]
        assert "OrderRepository" in repo_names
        assert "CustomerRepository" in repo_names

    def test_execute_generates_rules_per_entity(self):
        from agent import BackendAgent
        agent = BackendAgent()
        result = agent.execute({
            "project_id": str(uuid.uuid4()),
            "entities": [{"name": "User"}],
        })
        rule_names = [r["rule_name"] for r in result["rules"]]
        assert "UserValidationRule" in rule_names
        assert "UserAuthorizationRule" in rule_names

    def test_execute_openapi_spec_valid_json(self):
        from agent import BackendAgent
        agent = BackendAgent()
        result = agent.execute({
            "project_id": str(uuid.uuid4()),
            "entities": [{"name": "Item"}],
        })
        spec = json.loads(result["openapi_spec"])
        assert spec["openapi"] == "3.1.0"
        assert "/api/v1/items" in spec["paths"]

    def test_agent_registry_includes_backend_agent(self):
        from agent import agent_registry
        assert "BackendAgent" in agent_registry.list_registered_agents()

    def test_execute_task_compatibility_adapter(self):
        from agent import BackendAgent
        agent = BackendAgent()
        ctx = {"project_id": str(uuid.uuid4()), "workflow_id": str(uuid.uuid4())}
        result = agent.execute_task("Generate backend code", ctx)
        assert result["agent_id"] == "BackendAgent"
        assert result["status"] == "COMPLETED"
        assert isinstance(result["output"], dict)
        assert "services" in result["output"]

    def test_execute_generates_test_cases_for_each_entity(self):
        from agent import BackendAgent
        agent = BackendAgent()
        result = agent.execute({
            "project_id": str(uuid.uuid4()),
            "entities": [{"name": "Widget"}],
        })
        test_names = [t["test_name"] for t in result["test_reports"]]
        assert "test_create_widget" in test_names
        assert "test_list_widgets" in test_names


# ────────────────────────────────────────────────────────────────────────────
# 11. TestWorkflowManagerGate
# ────────────────────────────────────────────────────────────────────────────

class TestWorkflowManagerGate:

    def _make_manager(self):
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

    def test_on_backend_generation_completed_resumes_workflow(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {"project_id": str(uuid.uuid4())},
            "agent_outputs": {},
            "errors": [],
        }
        mgr.run_workflow_step = MagicMock(return_value={"status": "RUNNING"})

        result = mgr.on_backend_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
            result_summary={"endpoint_count": 10, "service_count": 3},
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "RUNNING"
        mgr.run_workflow_step.assert_called_once()

    def test_on_backend_generation_completed_updates_checkpoint(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {"project_id": "test-project"},
            "agent_outputs": {"ArchitectAgent": {"report_id": "arch-1"}},
            "errors": [],
        }
        mgr.run_workflow_step = MagicMock()

        mgr.on_backend_generation_completed(
            workflow_id=wf_id,
            generation_id=gen_id,
        )

        mgr.checkpoint_mgr.save_checkpoint.assert_called()
        save_args = mgr.checkpoint_mgr.save_checkpoint.call_args[1]
        assert save_args["agent_outputs"]["BackendAgent"]["generation_id"] == gen_id

    def test_on_backend_generation_completed_ignores_non_paused(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "RUNNING"

        result = mgr.on_backend_generation_completed(
            workflow_id=wf_id,
            generation_id=str(uuid.uuid4()),
        )

        assert result is False
        mgr._mock_event_pub.publish.assert_not_called()

    def test_on_backend_generation_failed_sets_failed_state(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        result = mgr.on_backend_generation_failed(
            workflow_id=wf_id,
            error="LLM quota exceeded",
        )

        assert result is True
        assert mgr.active_executions[wf_id] == "FAILED"
        mgr._mock_event_pub.publish.assert_called()

    def test_on_backend_generation_failed_publishes_error_events(self):
        mgr = self._make_manager()
        wf_id = str(uuid.uuid4())
        mgr.active_executions[wf_id] = "PAUSED"
        mgr.checkpoint_mgr.restore_checkpoint.return_value = {
            "execution_context": {},
            "agent_outputs": {},
            "errors": [],
        }

        mgr.on_backend_generation_failed(
            workflow_id=wf_id,
            error="Timeout after 30s",
        )

        published_topics = [
            call[0][0] for call in mgr._mock_event_pub.publish.call_args_list
        ]
        assert "workflow.events" in published_topics
        assert "workflow.errors" in published_topics
