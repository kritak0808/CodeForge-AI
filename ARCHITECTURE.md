# System Architecture & Design Blueprint

This document details the architectural foundation of CodeForge AI, an enterprise autonomous agentic software development system.

---

## 1. Overall System Architecture

CodeForge AI uses a decoupled, event-driven microservices architecture where backend APIs, a front-end client, independent worker pods, and a central orchestrator coordinate via Apache Kafka, PostgreSQL, and Redis.

```
       ┌────────────────────────────────────────────────────────┐
       │                    Next.js 15 Web UI                   │
       └───────────────────────────┬────────────────────────────┘
                                   │ HTTPS / REST
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                  FastAPI API Gateway                   │
       └─────┬─────────────────────┬──────────────────────┬─────┘
             │                     │                      │
             ▼ Read/Write          ▼ Cache/Limiter        ▼ Event Publish
     ┌──────────────┐      ┌──────────────┐      ┌────────────────┐
     │  PostgreSQL  │      │ Redis Cache  │      │  Apache Kafka  │
     └──────────────┘      └──────────────┘      └───────┬────────┘
                                                         │
                                                         ▼ Event Subscribe
       ┌─────────────────────────────────────────────────┴──────┐
       │             Autonomous SDLC Controller                 │
       │           (Orchestrated via LangGraph)                 │
       └─────┬────────────────────────────────────────────┬─────┘
             │                                            │
             ▼ Read/Write Checkpoints                     ▼ Dispatch Job Events
       ┌──────────────┐                          ┌────────┴───────┐
       │ Redis Check- │                          │  Agent Worker  │
       │ point Store  │                          │  Pool (CrewAI) │
       └──────────────┘                          └────────┬───────┘
                                                          │ Runs
                                                          ▼
                                                 ┌────────────────┐
                                                 │ 14 Specialized │
                                                 │ Agent Systems  │
                                                 └────────┬───────┘
                                                          │ Semantic Queries
                                                          ▼
                                                 ┌────────────────┐
                                                 │   Qdrant DB    │
                                                 └────────────────┘
```

---

## 2. The 14-Stage SDLC Agent Workflow

The platform automates software development by routing user requests through a linear-directed graph of specialized agents:

1. **Research Agent**: Analyzes public APIs, scans libraries, gathers documentation, and parses codebase contexts.
2. **Architect Agent**: Translates requirements into formal architecture blueprints and API specifications.
3. **Database Agent**: Formulates schema designs, entity diagrams, migration files, and SQL indexing rules.
4. **Backend Agent**: Implements the server code, REST routes, controllers, and dependency injection structures.
5. **Frontend Agent**: Builds user interfaces, design systems, routing structures, and connects backend APIs.
6. **QA Agent**: Reviews code changes, generates test cases, and runs automated unit and integration tests.
7. **Security Agent**: Reviews static code for vulnerabilities, runs secret scanning, and configures OWASP security headers.
8. **DevOps Agent**: Constructs Dockerfiles, Compose configurations, Kubernetes manifests, and Helm packages.
9. **Deployment Agent**: Automates container registries synchronization and launches Helm releases to EKS.
10. **Collaboration Engine**: Manages user notifications, Slack webhook integration, and manages manual approvals.
11. **Observability Platform**: Configures monitoring client metrics, distributed OpenTelemetry tracing, and Grafana alert boundaries.
12. **Cost Optimization Agent**: Parses token consumption, compute costs, and outputs database storage optimization plans.
13. **Autonomous SDLC Controller**: Evaluates steps health, monitors memory, schedules automatic retries, and decides rollback actions.

---

## 3. Communication & Event Streaming (Apache Kafka)

Services communicate asynchronously using Kafka topics to avoid tight coupling:

* **`sdlc.controller.started`**: Fired when the Autonomous Controller kicks off a new project SDLC pipeline.
* **`agent.job.dispatched`**: Dispatched by the orchestrator to request work from a specialized worker.
* **`agent.job.completed`**: Published by agent workers upon successful execution of their tasks.
* **`agent.job.failed`**: Dispatched when an agent worker encounters an unrecoverable failure.
* **`approval.requested`**: Fired when an agent requires manual sign-off (e.g. database schema change, production deployment).
* **`approval.responded`**: Fired when a user approves or rejects an active approval gate.

---

## 4. State Management & Checkpointing

* **Database (PostgreSQL)**: Acts as the primary transactional datastore. Holds metadata on `projects`, `users`, `workflows`, `audit_logs`, `agent_health`, and `cost_records`.
* **State Checkpointing (Redis)**: LangGraph uses Redis as a persistent checkpointer to save execution state variables, agent outputs, and step histories. This allows long-running developer loops to survive crashes and resume seamlessly.
* **Semantic Storage (Qdrant)**: Houses vector embeddings of requirements, repositories source code, and API logs to allow agents to search the codebase contextually.

---

## 5. Security & Access Control

* **Authentication**: JWT-based login with cryptographic signature verification.
* **Role-Based Access Control (RBAC)**: Supports roles (`Admin`, `Developer`, `Auditor`) to restrict deployment actions, database modifications, and billing queries.
* **Secrets Management**: Credentials (AWS Keys, DB passwords, LLM API tokens) are mounted as Kubernetes secrets and never logged or exposed in client responses.
