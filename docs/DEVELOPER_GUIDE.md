# Developer Guide

Welcome to the CodeForge AI developer guide! This document provides information on how to set up the development environment, contribute code, run tests, and follow our development standards.

---

## 1. Monorepo Structure

CodeForge AI uses a monorepo structure containing Python services/packages and a Next.js frontend:

*   **`apps/`**: Applications and services:
    *   `api`: FastAPI Backend gateway & Auth (JWT + RBAC).
    *   `agent-orchestrator`: LangGraph workflow engine.
    *   `agent-workers`: CrewAI worker processes executing agent tools.
    *   `approval-service`: Human-in-the-loop approval coordinator.
    *   `notification-service`: Kafka-driven email and slack dispatcher.
    *   `web`: Next.js 15 Web Console frontend.
*   **`packages/`**: Shared libraries:
    *   `shared-llm`: Unified LLM provider abstraction, token counting, cost tracking, and fallback handling.
    *   `shared-memory`: Base DB schemas, Redis task queue, and Qdrant vector retrieval.
*   **`infrastructure/`**: Deployment configurations:
    *   `docker`: Dockerfiles and compose setups.
    *   `kubernetes`: Helm charts for production deployments.
    *   `terraform`: AWS provisioning setup.

---

## 2. Setting Up Python Services

We use Poetry (or standard Virtual Environments) for Python packaging.

### virtualenv Setup
To run python tools, activate the target environment:
```bash
# Example for apps/api
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### shared packages
When developing, install shared packages in editable mode:
```bash
pip install -e ../../packages/shared-llm
pip install -e ../../packages/shared-memory
```

---

## 3. Running Backend Tests

We use `pytest` for all Python backend tests. To run all backend tests:
```bash
# Make sure python path is set to the api application directory
$env:PYTHONPATH="apps/api"
python -m pytest apps/api/tests/ -v
```

To run individual test files:
```bash
$env:PYTHONPATH="apps/api"
python -m pytest apps/api/tests/test_auth.py -v
```

---

## 4. Frontend Development

The frontend is a React application built with Next.js 15.

```bash
cd apps/web
npm install
npm run dev
```

The web interface will run on `http://localhost:3000`.

---

## 5. Development Guidelines

1.  **Strict Type Checking**: Keep python types annotated in services and TypeScript types enforced in the frontend.
2.  **Linting**: Run `ruff check .` for Python and `npm run lint` for Next.js.
3.  **No Mock Fallback in Production**: When environment variables for LLMs (`OPENAI_API_KEY`, etc.) are configured, the agents will utilize real LLM completion networks. Ensure your prompts do not result in unbounded or expensive iterations.
