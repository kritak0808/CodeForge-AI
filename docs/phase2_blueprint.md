# CodeForge AI - Phase 2 Monorepo Blueprint

This document specifies the service boundaries, development roadmap, event contracts, database migration plans, testing architectures, and CI/CD pipelines governing the implementation of the **CodeForge AI** Autonomous Software Engineering Operating System.

---

## 1. Repository Structure & Directory Map

The monorepo structure is established using JS/TS workspaces for the web and packaging layers, alongside isolated Python services.

```
codeforge-ai-monorepo/
├── apps/
│   ├── web/                     # Next.js 15 + TS admin and developer dashboard UI
│   ├── api/                     # FastAPI backend Gateway service
│   ├── agent-orchestrator/      # LangGraph stateful execution engine
│   ├── agent-workers/           # CrewAI multi-agent cooperative worker pool
│   ├── approval-service/        # Human-in-the-loop state controller
│   └── notification-service/    # Broadcast hub (Slack, SSE, email, etc.)
├── packages/
│   ├── shared-types/            # Common TypeScript models & definitions
│   ├── shared-config/           # Base configurations (tsconfig, formatting rules)
│   ├── shared-prompts/          # Shared system prompt templates for agents
│   ├── shared-events/           # Schema definitions and event models
│   └── shared-memory/           # Python drivers for Redis & Qdrant syncing
├── infrastructure/
│   ├── docker/                  # Dockerfiles & docker-compose configurations
│   ├── kubernetes/              # Helm charts and resources configurations
│   ├── terraform/               # IAC modules for AWS & OCI architectures
│   └── monitoring/              # Prometheus rule definitions & Grafana maps
└── docs/                        # Architecture design & system specifications
```

### Purpose of Key Folders
- `apps/web`: Admin/Dev console. Enables developers to trigger builds, view agent traces, and approve pending states.
- `apps/api`: REST gateway. Exposes routes for authentication, project assets, approval logs, and system metrics.
- `apps/agent-orchestrator`: LangGraph controller. Evaluates workflow transitions and publishes task orders to Kafka.
- `apps/agent-workers`: Role execution engine. Listens to Kafka task orders and compiles, builds, and edits source directories.
- `apps/approval-service`: Audit storage. Persists cryptographic signatures for human-approved changes.
- `apps/notification-service`: Broadcast manager. Sends realtime states to UI channels and notifications to external webhooks.
- `packages/shared-types`: Type definitions. Shares data model contracts between Next.js UI and shared packages.
- `packages/shared-config`: Monorepo settings. Enforces unified coding layouts.
- `packages/shared-prompts`: Agent instructions. Organizes reasoning behaviors under version control.
- `packages/shared-events`: Serialization schemas. Ensures format consistency across TS and Python producers/consumers.
- `packages/shared-memory`: Semantic caching drivers. Governs contextual data syncs.

---

## 2. Development Roadmap: Milestones 1-10

```mermaid
gantt
    title CodeForge AI Development Schedule
    dateFormat  YYYY-MM-DD
    section Backend Core
    M1: Auth & RBAC           :active, m1, 2026-07-01, 10d
    M2: Project Management     : m2, after m1, 10d
    M3: Workflow Engine        : m3, after m2, 14d
    section AI Layer
    M4: Agent Framework        : m4, after m3, 14d
    M5: Memory System          : m5, after m4, 10d
    M6: RAG System             : m6, after m5, 10d
    section Integration
    M7: Approval System        : m7, after m6, 7d
    M8: Sandbox Execution      : m8, after m7, 14d
    M9: Observability          : m9, after m8, 10d
    M10: Deployment Orchestrator: m10, after m9, 14d
```

### Milestone 1: Authentication & RBAC
- **Objectives**: Implement secure login, refresh token flows, and RBAC evaluation.
- **Dependencies**: PostgreSQL initialized with user schema.
- **Deliverables**: Auth route endpoints, JWT verification middleware, role profiles (Dev, Approver, Admin, Auditor).
- **Risks**: Token theft or credential leakage. Mitigated by short-lived JWT (15 mins) and sliding refresh tokens stored in HTTP-only cookies.
- **Testing**: Integration tests validating unauthorized access blocking.

### Milestone 2: Project Management
- **Objectives**: Establish project workspaces, directory managers, and database bindings.
- **Dependencies**: Milestone 1 (RBAC authorization).
- **Deliverables**: Project schemas, file explorer endpoints, directory volume attachments.
- **Risks**: Path traversal exploits. Mitigated by strict file path normalization checking in the backend.
- **Testing**: Unit tests checking parent directory traversal locks.

### Milestone 3: Workflow Engine
- **Objectives**: Build the state machine utilizing LangGraph checkpoints in PostgreSQL.
- **Dependencies**: Milestone 2.
- **Deliverables**: Workflow state machine script, checkpoint persistence configurations, pause/resume commands.
- **Risks**: Race conditions in multi-workflow steps. Mitigated by implementing workflow level row-locking in PostgreSQL.
- **Testing**: Deterministic workflow state transition path tests.

### Milestone 4: Agent Framework
- **Objectives**: Implement the core agent loop using CrewAI and connect agents to Kafka.
- **Dependencies**: Milestone 3.
- **Deliverables**: Agent worker runners, task listener consumer loops, prompt template loader bindings.
- **Risks**: Infinite loop reasoning cycles. Mitigated by strict `max_iterations` boundaries on LLM requests.
- **Testing**: Mock task verification check testing.

### Milestone 5: Memory System
- **Objectives**: Establish short-term Redis cache, semantic Qdrant vectors, and PostgreSQL memory tables.
- **Dependencies**: Milestone 4.
- **Deliverables**: Python shared memory utility package, Qdrant cluster collections, memory sync scripts.
- **Risks**: Memory drift or stale context matching. Mitigated by timestamp-based reciprocal rank fusion (RRF).
- **Testing**: Semantic retrieval accuracy validation tests.

### Milestone 6: RAG System
- **Objectives**: Build data ingestion, chunking, and embedding engines.
- **Dependencies**: Milestone 5.
- **Deliverables**: AST parser, parent-child chunkers, dense-retrieval pipeline.
- **Risks**: Embedding high-noise files (e.g. build logs). Mitigated by file-extension exclusionary filter rules.
- **Testing**: Document search precision benchmarking.

### Milestone 7: Approval System
- **Objectives**: Implement security approvals, DDL approvals, and audit logging.
- **Dependencies**: Milestone 3.
- **Deliverables**: Approval storage APIs, cryptographic signature verifiers, webhook notification triggers.
- **Risks**: Key forgery or signature bypass. Mitigated by verifying payload integrity with SHA256 hashes signed with user credentials.
- **Testing**: Signature validation and tampering tests.

### Milestone 8: Sandbox Execution
- **Objectives**: Configure gVisor sandboxes and secure shell runners.
- **Dependencies**: Milestone 4.
- **Deliverables**: Ephemeral build run scripts, network rules, resource usage monitors.
- **Risks**: Host system container escapes. Mitigated by rootless execution and locking kernel system calls via gVisor runtime.
- **Testing**: Exploit penetration testing (attempting container escapes).

### Milestone 9: Observability
- **Objectives**: Integrate OpenTelemetry trace logging and token expense metrics.
- **Dependencies**: Milestones 1-8.
- **Deliverables**: OpenTelemetry collector configuration, Prometheus export endpoints, Grafana dashboard charts.
- **Risks**: Telemetry logging overhead impacting service latencies. Mitigated by asynchronous batch trace exports.
- **Testing**: Load testing trace generation.

### Milestone 10: Deployment
- **Objectives**: Build target cluster configurations, deployment agents, and rollbacks.
- **Dependencies**: Milestone 8 & 9.
- **Deliverables**: EKS deploy scripts, Helm configurations, deployment monitor services.
- **Risks**: Failed updates causing platform downtime. Mitigated by standard Blue-Green deployment and rollback steps.
- **Testing**: Chaos testing (killing pods to confirm healing).

---

## 3. Service Boundaries & Contexts

```
                      +-------------------+
                      |   Next.js 15 UI   |
                      +-------------------+
                                |
                                v
                      +-------------------+
                      |    FastAPI API    |
                      +-------------------+
                        /               \
                       /                 \
                      v                   v
            +-------------------+   +--------------------+
            |    Orchestrator   |   |  Approval Service  |
            +-------------------+   +--------------------+
                      |                       |
            +-------------------+             |
            |   Agent Workers   | <-----------+
            +-------------------+
```

### 3.1 API Service
- **Responsibilities**: Gateways requests, verifies authorizations, exposes file assets.
- **APIs**:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/projects`
  - `GET /api/v1/projects/{id}/files`
  - `GET /api/v1/workflows/{id}/traces`
- **Events Published**: `project.created`, `workflow.triggered`.
- **Events Consumed**: `workflow.events` (for UI dashboard SSE updates).
- **Database Access Patterns**: Direct Read/Write access to `users`, `projects`, `audit_logs`, and read-only access to `metrics` tables.

### 3.2 Orchestrator Service
- **Responsibilities**: Runs stateful workflows, coordinates state transitions.
- **APIs**: None (internally triggered by event brokers).
- **Events Published**: `workflow.events`, `agent.tasks`.
- **Events Consumed**: `workflow.triggered`, `agent.replies`, `approval.events`.
- **Database Access Patterns**: Read/Write to `workflows`, `workflow_states`, `tasks`, `approvals`.

### 3.3 Agent Worker Service
- **Responsibilities**: Executes code commands, performs lint checks, runs test commands in sandboxes.
- **APIs**: None.
- **Events Published**: `agent.replies`, `observability.telemetry`.
- **Events Consumed**: `agent.tasks`.
- **Database Access Patterns**: Read-only access to `projects`, `agents`.

### 3.4 Memory Service
- **Responsibilities**: Syncs long-term and short-term data context.
- **APIs**: `POST /api/v1/memory/sync`, `GET /api/v1/memory/search`.
- **Events Published**: `memory.synced`.
- **Events Consumed**: `agent.replies`.
- **Database Access Patterns**: Direct Read/Write access to `agent_memory`, `project_memory` tables.

### 3.5 RAG Service
- **Responsibilities**: Parses source documents, queries vector indexes.
- **APIs**: `POST /api/v1/rag/ingest`, `POST /api/v1/rag/query`.
- **Events Published**: None.
- **Events Consumed**: None.
- **Database Access Patterns**: Read/Write access to `knowledge_sources`, `documents`, `embeddings`.

### 3.6 Approval Service
- **Responsibilities**: Locks states, validates signatures, captures audit trails.
- **APIs**:
  - `GET /api/v1/approvals/pending`
  - `POST /api/v1/approvals/{id}/decision`
- **Events Published**: `approval.events` (approval details/decision).
- **Events Consumed**: `workflow.events`.
- **Database Access Patterns**: Read/Write access to `approvals`, `audit_logs`.

### 3.7 Notification Service
- **Responsibilities**: Channels message alerts (SSE/Webhooks/Email).
- **APIs**: `GET /api/v1/notifications/stream`.
- **Events Published**: None.
- **Events Consumed**: `workflow.events`, `approval.events`, `deployment.events`.
- **Database Access Patterns**: Read/Write access to `notifications`.

---

## 4. Event Contracts (Kafka)

All events must adhere to validation schemas using Avro or JSON Schema protocols.

### 4.1 Schema Definitions (JSON Schema Format)

#### Topic: `workflow.events`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WorkflowStateEvent",
  "type": "object",
  "properties": {
    "eventId": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "correlationId": { "type": "string", "format": "uuid" },
    "workflowId": { "type": "string", "format": "uuid" },
    "projectId": { "type": "string", "format": "uuid" },
    "oldState": { "type": "string", "enum": ["INITIATED", "ARCHITECTING", "DEVELOPING", "TESTING", "SECURITY_AUDITING", "PENDING_APPROVAL", "DEPLOYING", "COMPLETED", "FAILED"] },
    "newState": { "type": "string", "enum": ["INITIATED", "ARCHITECTING", "DEVELOPING", "TESTING", "SECURITY_AUDITING", "PENDING_APPROVAL", "DEPLOYING", "COMPLETED", "FAILED"] }
  },
  "required": ["eventId", "timestamp", "correlationId", "workflowId", "projectId", "newState"]
}
```

#### Topic: `agent.tasks`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentTaskEvent",
  "type": "object",
  "properties": {
    "taskId": { "type": "string", "format": "uuid" },
    "workflowId": { "type": "string", "format": "uuid" },
    "agentId": { "type": "string" },
    "command": { "type": "string" },
    "payload": { "type": "object" },
    "correlationId": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["taskId", "workflowId", "agentId", "command", "payload", "correlationId", "timestamp"]
}
```

#### Topic: `agent.replies`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentReplyEvent",
  "type": "object",
  "properties": {
    "taskId": { "type": "string", "format": "uuid" },
    "workflowId": { "type": "string", "format": "uuid" },
    "agentId": { "type": "string" },
    "status": { "type": "string", "enum": ["SUCCESS", "FAILED"] },
    "result": { "type": "object" },
    "correlationId": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["taskId", "workflowId", "agentId", "status", "result", "correlationId", "timestamp"]
}
```

#### Topic: `approval.events`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ApprovalDecisionEvent",
  "type": "object",
  "properties": {
    "approvalId": { "type": "string", "format": "uuid" },
    "workflowId": { "type": "string", "format": "uuid" },
    "decision": { "type": "string", "enum": ["APPROVED", "REJECTED"] },
    "comments": { "type": "string" },
    "signature": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["approvalId", "workflowId", "decision", "signature", "timestamp"]
}
```

### 4.2 Producers and Consumers Mapping
- `workflow.events`: Produced by Orchestrator; Consumed by API Gateway, Notification Service.
- `agent.tasks`: Produced by Orchestrator; Consumed by Agent Workers.
- `agent.replies`: Produced by Agent Workers; Consumed by Orchestrator.
- `approval.events`: Produced by Approval Service; Consumed by Orchestrator.

### 4.3 Message Validation Rules
1. **Schema Check**: Consumers validate message payload against registered JSON schema upon receipt. Failure drops payload directly to Dead Letter Queue (DLQ).
2. **Signature Verification**: Events containing structural updates (e.g. Database schema adjustments) must contain cryptographically verified user signatures.

---

## 5. Database Migration Strategy

All database schemas are updated and deployed using Alembic migrations in structured steps.

```
[M001: Users & Projects] --> [M002: Workflow Engine State] --> [M003: Tasks & Logs]
                                                                        |
                                                                        v
[M005: RAG & Metadata Mapping] <-- [M004: Approvals & Audit Trails] <----+
```

### 5.1 Migration Sequence Order
1. **`0001_initial_users_projects.py`**: Creates `users`, `projects`, and `agents` reference tables.
2. **`0002_workflows_and_states.py`**: Creates `workflows` and `workflow_states` tracking tables.
3. **`0003_tasks_and_memory.py`**: Creates `tasks` and `agent_memory`/`project_memory` data structures.
4. **`0004_approvals_and_audits.py`**: Creates `approvals`, `deployments`, and `audit_logs` collections.
5. **`0005_knowledge_and_documents.py`**: Creates `knowledge_sources`, `documents`, `embeddings`, and `notifications`.

### 5.2 Database Seed Data Strategy
- **Base Seeding**: The migration framework applies seed configurations to populate the `agents` reference table with details for the 12 specialized developer roles (name, default models, guidelines).
- **Mock Seeding**: Development environments execute `python seed_mock_data.py` to populate initial users, dummy active tasks, and mock trace metrics.

### 5.3 Database Rollback Strategy
- Every migration migration file implements a detailed `downgrade()` function to drop tables and tablespaces.
- **Rollback Runbook**: Before applying updates, DB snapshots are captured. If validation tests fail post-migration, the system runs `alembic downgrade -1` or restores from snapshots.

---

## 6. CI/CD Pipeline & Environments

```
[Local Workstation]  -->  Local Dev (Docker-Compose, mock APIs, local SQLite)
        |
    [Git Push]
        v
[GitHub Actions CI]  -->  Staging Cluster (AWS EKS Staging, RDS PostgreSQL)
        |
  [HITL Approved]
        v
[GitHub Actions CD]  -->  Production Cluster (AWS EKS Prod, RDS Aurora DB)
```

### 6.1 Local Development Workflow
- Developers run local configurations using `docker-compose up` inside the `infrastructure/docker` directory.
- Developers execute code changes inside local workspaces. Mock registries are used to supply dependency modules, isolating execution local networks.

### 6.2 Staging Pipeline Workflow
- Commits pushed to the `staging` branch trigger automated GitHub Actions runners.
- The pipeline compiles the containers, runs full unit suites, performs lint tests, and releases configurations to EKS Staging.

### 6.3 Production CD Pipeline Workflow
- Pull requests merged into the `main` branch trigger production builds.
- Releases pause for human-in-the-loop validation check verification.
- Upon approval, the Helm chart deploys changes to the EKS Production cluster, applying database migrations before updating pods.

---

## 7. Testing Architecture

Testing is split across four execution tiers:

```
+--------------------------------------------------------+
|                  Testing Architecture                  |
+--------------------------------------------------------+
  - Unit Tier        : PyTest/Vitest (isolated calculations)
  - Integration Tier : TestContainers (DB and Kafka locks)
  - Contract Tier    : Pact framework (event payload checks)
  - E2E Tier         : Playwright (requirements to deploy)
```

### 7.1 Unit & Integration Testing Strategy
- **Unit Tier**: Runs using PyTest for python services and Vitest for TS modules, validating isolated helper routines (e.g. token expense estimations).
- **Integration Tier**: Uses the **Testcontainers** library to launch ephemeral instances of PostgreSQL, Kafka, and Redis, testing database lock allocations and consumer queues.

### 7.2 Contract & E2E Testing Strategy
- **Contract Tier**: Uses the **Pact** contract testing framework, checking that message schemas published on Kafka match parameters defined in consumers.
- **E2E Tier**: Simulates user runs (e.g., creating project, drafting database schema, submitting approvals) using **Playwright** against a fully deployed staging environment.
