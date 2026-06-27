# Security Policy

This document describes the security practices, vulnerability reporting procedures, and architectural security controls implemented in CodeForge AI.

---

## 1. Core Security Safeguards

We design and deploy services following security-first principles:

* **Authentication (JWT)**: Users authenticate using JWT bearer tokens signed with a HS256 algorithm. Tokens have a short expiration window (15 minutes).
* **Role-Based Access Control (RBAC)**: All administrative and write operations (e.g., executing database migrations, viewing billing details, deploying to staging/production) require verified roles (`Admin` or `Developer`).
* **Secrets Protection**: Secrets (LLM API keys, database credentials, AWS IAM keys) are never checked into git, written to logs, or serialized in API responses. They are injected as environment variables or mounted via Kubernetes secrets.
* **Rate Limiting**: API routes are protected by a Redis-backed token bucket rate limiter to prevent Denial of Service (DoS) and brute force attacks.
* **OWASP Security Headers**: Next.js and FastAPI backends enforce secure HTTP response headers, including Content Security Policy (CSP), Strict-Transport-Security (HSTS), X-Frame-Options, and X-Content-Type-Options.

---

## 2. DevSecOps & Pipeline Scanning

Our CI/CD pipelines run automated security sweeps:

1. **Static Analysis & Linting**: Ruff scans python services for insecure coding structures (e.g. use of `eval`, insecure random number generators).
2. **Container Security**: Container images are scanned by **Trivy** during build stages to identify known CVEs in system libraries.
3. **Secret Scanning**: **Gitleaks** checks commits for accidentally exposed credentials.

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability, please do **NOT** open a public issue. Instead, report it responsibly:

1. Send an email to `security@codeforge.ai`.
2. Include a detailed description of the vulnerability, steps to reproduce, and any proof-of-concept material.
3. We will acknowledge receipt of your report within 48 hours and work with you to release a patch.
