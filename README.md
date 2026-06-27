# 🚀 CodeForge AI

<div align="center">

![CodeForge AI](https://img.shields.io/badge/CodeForge-AI-6C63FF?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge\&logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge\&logo=next.js)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-blue?style=for-the-badge)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-orange?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge\&logo=python)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue?style=for-the-badge\&logo=typescript)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

### Enterprise Autonomous Software Development Life Cycle (SDLC) Platform

**From Requirements → Architecture → Development → Testing → Deployment → Monitoring**

🌐 **Live Demo:** https://code-forge-ai-ivory.vercel.app/

</div>

---

# 📖 Overview

CodeForge AI is a fully autonomous, enterprise-grade **Agentic Software Development Life Cycle (SDLC)** platform that transforms software ideas into production-ready applications using specialized AI agents.

Unlike traditional AI coding assistants, CodeForge AI orchestrates an intelligent multi-agent ecosystem capable of managing the entire SDLC—from project planning and software architecture to deployment, monitoring, and continuous optimization.

The platform combines autonomous reasoning, workflow orchestration, event-driven microservices, infrastructure automation, and enterprise observability into a single production-ready ecosystem.

---

# ✨ Features

## 🤖 Autonomous Multi-Agent System

* 14 Specialized AI Agents
* Intelligent Workflow Orchestration
* Human-in-the-loop Approval Gates
* Autonomous Recovery & Retry Logic
* Event Driven Architecture

---

## 🏗 Enterprise SDLC Automation

* Requirements Analysis
* Software Architecture Generation
* Database Design
* Backend API Generation
* Frontend Generation
* QA Automation
* Security Audits
* Infrastructure Provisioning
* Deployment Automation
* Cost Optimization
* Production Monitoring

---

## ⚡ Production Features

* JWT Authentication
* Role Based Access Control (RBAC)
* Project Management
* Workflow Engine
* Audit Logging
* API Gateway
* Background Workers
* Health Monitoring
* Cost Dashboard
* Real-Time Agent Status
* Metrics Dashboard

---

# 🌐 Live Demo

### Frontend

https://code-forge-ai-ivory.vercel.app/

### Backend API

https://web-production-a7ee2.up.railway.app

### API Documentation

https://web-production-a7ee2.up.railway.app/docs

---

# 🏛 Architecture

```
                    User
                      │
                      ▼
             Next.js Web Dashboard
                      │
                      ▼
              FastAPI API Gateway
                      │
 ────────────────────────────────────────────
 │          Authentication & RBAC            │
 │          Workflow Controller              │
 │          Project Manager                  │
 │          Event Publisher                  │
 ────────────────────────────────────────────
                      │
                Apache Kafka
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
 Research Agent   Backend Agent   Frontend Agent
      ▼               ▼                ▼
 QA Agent       Security Agent    DevOps Agent
      ▼               ▼                ▼
 Deployment      Monitoring      Cost Optimizer
                      │
                      ▼
               Production Platform
```

---

# 🤖 Agent Ecosystem

| Agent                   | Responsibility         |
| ----------------------- | ---------------------- |
| Research Agent          | Requirement Analysis   |
| Architecture Agent      | System Design          |
| Database Agent          | Database Modeling      |
| Backend Agent           | API Development        |
| Frontend Agent          | UI Generation          |
| QA Agent                | Automated Testing      |
| Security Agent          | Vulnerability Analysis |
| DevOps Agent            | CI/CD Pipelines        |
| Deployment Agent        | Production Releases    |
| Collaboration Agent     | Team Coordination      |
| Observability Agent     | Monitoring             |
| Cost Optimization Agent | Cloud Cost Analysis    |
| Enterprise Agent        | Governance             |
| Autonomous Controller   | Workflow Orchestration |

---

# 🛠 Tech Stack

## Frontend

* Next.js 15
* React 19
* TypeScript
* TailwindCSS
* ShadCN UI
* TanStack Query

---

## Backend

* FastAPI
* Python 3.12
* SQLAlchemy
* Alembic
* Pydantic v2
* JWT Authentication

---

## AI Framework

* LangGraph
* CrewAI
* OpenAI
* Gemini
* Anthropic

---

## Infrastructure

* PostgreSQL
* Redis
* Apache Kafka
* Docker
* Kubernetes
* Terraform
* GitHub Actions

---

## Monitoring

* Prometheus
* Grafana
* OpenTelemetry

---

# 📂 Repository Structure

```text
codeforge-ai/
│
├── apps/
│   ├── api/
│   ├── web/
│   ├── agent-orchestrator/
│   ├── agent-workers/
│   ├── approval-service/
│   └── notification-service/
│
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   └── terraform/
│
├── packages/
│
├── docs/
│
└── tests/
```

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/kritak0808/CodeForge-AI.git

cd CodeForge-AI
```

---

## Backend

```bash
cd apps/api

poetry install

uvicorn app.main:app --reload
```

---

## Frontend

```bash
cd apps/web

pnpm install

pnpm dev
```

---

## Docker

```bash
docker compose up -d
```

---

# 🔐 Authentication

Default Development Credentials

```
Username : admin

Password : admin123
```

---

# 📊 Platform Capabilities

* Multi-Agent Coordination
* Event Driven Workflows
* Human Approval Gates
* Enterprise Authentication
* Real-Time Monitoring
* Workflow Visualization
* Project Management
* Infrastructure Automation
* Security Scanning
* Cost Optimization
* Production Deployment
* Audit Logging

---

# 🧪 Testing

Run Backend Tests

```bash
pytest apps/api/tests -v
```

Run Full Verification

```bash
python scratch/run_tests.py
```

---

# 📸 Screens

* Login Dashboard
* Autonomous SDLC Dashboard
* Project Management
* Workflow Monitoring
* Agent Status
* Cost Analytics
* Approval Center
* Observability Dashboard

---

# 📈 Roadmap

* AI Code Review
* Multi-Cloud Deployment
* GitHub Repository Generation
* Autonomous Pull Requests
* Kubernetes Auto Scaling
* AI Architecture Review
* Self-Healing Workflows
* LLM Fine-Tuning
* Multi-Tenant SaaS Support

---

# 👨‍💻 Author

**Kritak Prasad**

B.Tech Computer Science & Engineering

SRM Institute of Science and Technology

GitHub: https://github.com/kritak0808

---

# ⭐ Support

If you found this project helpful, consider giving it a ⭐ on GitHub.

---

<div align="center">

### CodeForge AI

**Autonomous Software Engineering Powered by Multi-Agent Intelligence**

Made with ❤️ using FastAPI, Next.js, LangGraph & CrewAI

</div>
