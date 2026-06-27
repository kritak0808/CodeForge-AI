# Production Deployment Guide

This guide provides setup and deployment instructions for CodeForge AI, covering local development, containerized production, Kubernetes orchestrations, and Terraform provisioning on AWS.

---

## 1. Environment Variables Configuration

Create a `.env` file in the root directory based on the following reference table:

| Environment Variable | Description | Example Value |
| -------------------- | ----------- | ------------- |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@localhost:5432/codeforge` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers list | `localhost:9092` |
| `QDRANT_URL` | Qdrant DB connection endpoint | `http://localhost:6333` |
| `JWT_SECRET` | Cryptographic key for signing JWTs | `super-secret-key-change-in-production` |
| `OPENAI_API_KEY` | LLM service key | `sk-proj-xxxxxxxx` |
| `ENVIRONMENT` | Target execution environment | `development` or `production` |

---

## 2. Containerized Deployment

### 2.1 Local Development (Docker Compose)
To launch the dependency infrastructure (databases, caches, streams) locally:
```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```
Verify containers are running:
```bash
docker ps
```

### 2.2 Production Container Stack
To launch the entire platform (services and databases) using the production profile with resource constraints and health checks:
```bash
docker compose -f infrastructure/docker/docker-compose.prod.yml up -d --build
```
This boots optimized multi-stage images, isolates database networks, and enforces read-only volumes where applicable.

---

## 3. Kubernetes Deployment (Helm)

The Kubernetes deployment uses Helm to orchestrate deployments, services, HPAs, and persistent volumes under `infrastructure/kubernetes/codeforge-chart/`.

### 3.1 Prerequisite Setup
Ensure you have ingress controllers configured and secrets mapped:
```bash
kubectl create namespace codeforge-production
kubectl create secret generic codeforge-secrets \
  --from-literal=database-url="postgresql://user:pass@postgres-service:5432/codeforge" \
  --from-literal=openai-api-key="sk-..." \
  --namespace codeforge-production
```

### 3.2 Helm Chart Installation
Dry-run templates compilation to verify configs:
```bash
helm template codeforge-release infrastructure/kubernetes/codeforge-chart
```

Install or upgrade the chart:
```bash
helm upgrade --install codeforge-production infrastructure/kubernetes/codeforge-chart \
  --namespace codeforge-production \
  --values infrastructure/kubernetes/codeforge-chart/values.yaml
```

Verify deployment rollouts:
```bash
kubectl get deployments -n codeforge-production
kubectl get pods -n codeforge-production
```

---

## 4. AWS Cloud Provisioning (Terraform)

Terraform configures the complete network layout, database instances, streaming clusters, and Kubernetes resources on AWS.

### 4.1 Prerequisites
Ensure AWS CLI is logged in and Terraform is installed:
```bash
aws sts get-caller-identity
```

### 4.2 Provisioning Workflow
Initialize Terraform configurations under `infrastructure/terraform/`:
```bash
cd infrastructure/terraform
terraform init
```

Generate and inspect the execution plan:
```bash
terraform plan -out=tfplan
```

Apply changes to provision AWS EKS, RDS, ElastiCache, and MSK:
```bash
terraform apply tfplan
```

### 4.3 EKS Kubeconfig Integration
Connect `kubectl` to the newly provisioned AWS EKS cluster:
```bash
aws eks update-kubeconfig --name codeforge-production-eks --region us-east-1
```
Now, proceed with the Helm installation steps above.
