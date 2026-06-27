# Contributing to CodeForge AI

We welcome contributions to CodeForge AI. To maintain high code quality and security, please follow these guidelines.

---

## 1. Local Development Setup

CodeForge AI is organized as a monorepo.
* **Frontend**: Next.js (located in `apps/web`) managed using `pnpm` workspaces.
* **Backend Services**: Python-based services (located under `apps/` and `packages/`) managed using `poetry`.

### Monorepo Setup Checklist

1. Clone the repository and initialize node dependencies:
   ```bash
   pnpm install
   ```
2. Navigate to each Python service and configure virtual environments:
   ```bash
   cd apps/api
   poetry install
   ```
3. Run the development docker compose stack:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.yml up -d
   ```

---

## 2. Coding Standards & Tooling

To ensure consistency across the monorepo, we enforce automated styling and linting checks.

### Python Code
We use **Ruff** for linting and formatting. Run checks locally before committing:
```bash
poetry run ruff check .
poetry run ruff format .
```

### TypeScript / JavaScript Code
We use **ESLint** and **Prettier** for the frontend. Run checks via:
```bash
pnpm run lint
pnpm run format
```

---

## 3. Commit Message Guidelines

We follow **Conventional Commits**:
* `feat`: A new feature (e.g., `feat(api): add route for workflow rollback`)
* `fix`: A bug fix (e.g., `fix(orchestrator): resolve checkpoint lookup failure`)
* `docs`: Documentation updates (e.g., `docs(deployment): add AWS EKS steps`)
* `style`: Styling changes that do not affect code logic (formatting)
* `refactor`: Structural edits that neither fix bugs nor add features
* `test`: Adding or correcting tests

Example:
```git
feat(workers): implement Trivy container scanning agent
```

---

## 4. Pull Request Checklist

Before opening a pull request, ensure:
1. All unit, integration, and API tests pass:
   ```bash
   python scratch/run_tests.py
   ```
2. Ruff linter reports zero errors.
3. ESLint validations pass on the client code.
4. Your branch contains clear, readable documentation updates if APIs or configurations changed.
