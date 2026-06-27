# CodeForge AI - API Reference Guide

This document catalogs the REST API endpoints exposed by the CodeForge AI Gateway (`apps/api`).

---

## 1. Authentication & Authorization

All endpoints, except `/api/v1/auth/login` and `/health`, require an `Authorization` header containing a valid JWT bearer token.

```http
Authorization: Bearer <your_jwt_token>
```

### POST `/api/v1/auth/login`
Exchanges user credentials for a JWT token.

* **Request Body**:
  ```json
  {
    "username": "developer",
    "password": "secure-password"
  }
  ```
* **Success Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

## 2. Project Management

### GET `/api/v1/projects`
Retrieves a list of projects. Supports pagination parameters (`skip`, `limit`).

* **Success Response (200 OK)**:
  ```json
  [
    {
      "id": "proj_01j123456",
      "name": "E-Commerce Gateway",
      "description": "API microservice for order routing",
      "created_at": "2026-06-25T12:00:00Z"
    }
  ]
  ```

### POST `/api/v1/projects`
Creates a new project.

* **Request Body**:
  ```json
  {
    "name": "E-Commerce Gateway",
    "description": "API microservice for order routing"
  }
  ```

---

## 3. Autonomous SDLC Controller & Workflows

### POST `/api/v1/controller/workflows`
Starts a new SDLC workflow run for a project.

* **Request Body**:
  ```json
  {
    "project_id": "proj_01j123456",
    "initial_prompt": "Build a secure REST API with user signup and login"
  }
  ```
* **Success Response (201 Created)**:
  ```json
  {
    "workflow_id": "wf_987654321",
    "status": "started",
    "current_stage": "Research"
  }
  ```

### POST `/api/v1/controller/workflows/{workflow_id}/pause`
Pauses an active workflow run.

### POST `/api/v1/controller/workflows/{workflow_id}/resume`
Resumes a paused workflow run.

### POST `/api/v1/controller/workflows/{workflow_id}/cancel`
Cancels an active workflow run.

### POST `/api/v1/controller/workflows/{workflow_id}/retry`
Triggers an immediate retry of a failed stage.

* **Request Body**:
  ```json
  {
    "stage": "Backend",
    "reason": "Retry after resolving connection pool limits"
  }
  ```

### POST `/api/v1/controller/workflows/{workflow_id}/rollback`
Rolls back a workflow to a previously completed stable stage checkpoint.

* **Request Body**:
  ```json
  {
    "target_stage": "Database"
  }
  ```

---

## 4. Cost Optimization & Metrics

### GET `/api/v1/costs/report`
Retrieves aggregated cost analysis, including token usage, storage pricing, and infrastructure costs.

* **Query Parameters**:
  * `project_id` (string, optional)
* **Success Response (200 OK)**:
  ```json
  {
    "total_cost_usd": 142.50,
    "breakdown": {
      "llm_tokens": 82.10,
      "compute_k8s": 45.40,
      "storage_qdrant": 15.00
    },
    "recommendations": [
      {
        "agent": "BackendAgent",
        "description": "Cache embeddings to save 12% token overhead"
      }
    ]
  }
  ```

---

## 5. Health Checks

### GET `/health`
Verifies api container health and checks backend connections.

* **Success Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "services": {
      "postgres": "connected",
      "redis": "connected",
      "kafka": "connected"
    }
  }
  ```
