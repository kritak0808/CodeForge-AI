# CodeForge AI

CodeForge AI is a fully autonomous, enterprise-grade Agentic Software Development Life Cycle (SDLC) platform. It orchestrates 14 specialized agent subsystems to go from user requirements to production-ready deployments with automated testing, security scanning, infrastructure provisioning, and continuous cost optimization.

Built with a robust architecture leveraging FastAPI, Next.js 15, LangGraph, CrewAI, PostgreSQL, Redis, Apache Kafka, Qdrant, Docker, Kubernetes, and Terraform.

---

## 🚀 Key Features

* **14 Specialized Agent Roles**: Orchestrates specialized agents for Research, Architecture, Database, Backend, Frontend, QA, Security, DevOps, Deployment, Collaboration, Observability, Cost Optimization, and Autonomous Control.
* **Autonomous SDLC Controller**: Centrally monitors the SDLC, dynamically routes tasks, detects failures, issues retries/rollbacks, and ensures budget/approval-aware execution.
* **Event-Driven Microservices**: Processes asynchronous workloads via Apache Kafka, allowing independent agent workers to scale and interact seamlessly.
* **Production-Ready Multi-Tenant API**: Structured REST endpoints for user authentication (JWT/RBAC), project management, agent worker heartbeat logging, and audit logs.
* **Modern Next.js 15 Web Console**: Provides visual insight into ongoing agent reasoning, audit logs, real-time metrics, cost dashboards, and manual approval gates.
* **Full-Stack Observability**: Integrates OpenTelemetry, Prometheus, and Grafana for request-level metrics, distributed tracing, and real-time alerting.
* **Terraform Cloud Orchestration**: Provision production VPCs, Amazon EKS, AWS RDS (Postgres), Amazon ElastiCache (Redis), and Amazon MSK (Kafka) automatically.

---

## 🛠️ Technology Stack

* **Frontend**: Next.js 15 (App Router, TailwindCSS, TypeScript, pnpm)
* **Backend API**: FastAPI (Python 3.12, Poetry, Pydantic v2, SQLAlchemy)
* **Agent Framework**: LangGraph & CrewAI
* **Database**: PostgreSQL (Relational schema, SQLModel, Alembic)
* **Vector Store**: Qdrant (Semantic code/document retrieval)
* **Event Broker**: Apache Kafka (Event-driven message routing)
* **Caching & Checkpoints**: Redis (Rate limiting, task queues, and LangGraph checkpoints)
* **Infrastructure**: Docker Compose, Kubernetes (Helm), Terraform (AWS)
* **CI/CD**: GitHub Actions (Linting, pytest, Jest, Trivy security scan, Helm deployments)

---

## 📂 Repository Structure

```
codeforge-ai/
├── .github/workflows/         # CI/CD pipelines (GitHub Actions)
├── apps/
│   ├── api/                   # FastAPI Backend Gateway & Auth
│   ├── agent-orchestrator/    # LangGraph Central Coordinator
│   ├── agent-workers/         # CrewAI Agent Workers executor
│   ├── approval-service/      # Manual Gate / Human-in-the-loop server
│   ├── notification-service/  # Kafka-driven email/Slack dispatch
│   └── web/                   # Next.js 15 UI Web Console
├── packages/
│   └── shared-memory/         # Shared Redis state & DB schema bindings
├── infrastructure/
│   ├── docker/                # Local/Prod Compose configs & Dockerfiles
│   ├── kubernetes/            # Helm charts (deployments, ingress, HPAs)
│   └── terraform/             # AWS Cloud Automation (EKS, RDS, Redis, Kafka)
├── docs/                      # Architectural diagrams & design blueprints
└── tests/                     # Monorepo-wide integration and unit tests
```

---

## 🏁 Quickstart (Local Development)

### Prerequisites

* Docker & Docker Compose
* Node.js v20 (with `pnpm`)
* Python v3.12 (with `poetry`)

### Running the Whole Stack Locally

1. **Spin up Infrastructure Containers**:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.yml up -d
   ```
   This boots PostgreSQL, Redis, Kafka, and Qdrant.

2. **Run Backend API Gateway**:
   ```bash
   cd apps/api
   poetry install
   poetry run uvicorn app.main:app --reload --port 8000
   ```

3. **Run Agent Workers & Orchestrator**:
   ```bash
   cd apps/agent-orchestrator && poetry run python main.py
   cd apps/agent-workers && poetry run python main.py
   ```

4. **Run Next.js Web Console**:
   ```bash
   cd apps/web
   pnpm install
   pnpm run dev
   ```
   Access the dashboard at `http://localhost:3000`.

---

## 🧪 Testing and Verification

To run unit, integration, and end-to-end tests across the python services:
```bash
python -m pytest apps/api/tests/ -v
```

To run the monorepo-wide verification suite:
```bash
python scratch/run_tests.py
```

To run the automated 14-stage agent integration simulation:
```bash
python demo_workflow.py
```

---

## 📄 Documentation Index

For in-depth explanations of specific areas, refer to the following documents:
*   [Architecture Blueprint (ARCHITECTURE.md)](ARCHITECTURE.md)
*   [Production Deployment Guide (DEPLOYMENT.md)](DEPLOYMENT.md)
*   [API Reference & Schema Specifications (API.md)](API.md)
*   [Security Policy & Practices (SECURITY.md)](SECURITY.md)
*   [Developer Guide (docs/DEVELOPER_GUIDE.md)](docs/DEVELOPER_GUIDE.md)
*   [User Guide (docs/USER_GUIDE.md)](docs/USER_GUIDE.md)
*   [Production Readiness Report (docs/PRODUCTION_READINESS_REPORT.md)](docs/PRODUCTION_READINESS_REPORT.md)
*   [Contribution Guidelines (CONTRIBUTING.md)](CONTRIBUTING.md)
*   [System Changelog (CHANGELOG.md)](CHANGELOG.md)
*   [Software License (LICENSE)](LICENSE)

