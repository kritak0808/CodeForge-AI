# CodeForge AI — Frontend ↔ Backend Communication Fix

**Date:** 2026-06-26  
**Status:** ✅ Complete

---

## Problem

The login page displayed:

> "Unable to connect to the API. Is the backend running?"

The error came from `apps/web/src/app/login/page.tsx` — the generic catch branch fires when `fetch()` throws a network error (i.e., the request never reached the server).

---

## Root Cause Analysis

### Issue 1 — Port mismatch (CRITICAL)

| File | Variable | Was | Should be |
|------|----------|-----|-----------|
| `apps/web/.env.local` | `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8080` | `http://localhost:8000` |
| `apps/web/.env.local` | `NEXT_PUBLIC_WS_URL` | `ws://127.0.0.1:8080` | `ws://localhost:8000` |

The backend (`start-dev.ps1`, `run.py`) starts on **port 8000**.  
The frontend API client (`apps/web/src/lib/api.ts`) uses `NEXT_PUBLIC_API_URL` as the base URL.  
With the env pointing to `8080`, every `fetch()` call hit a port that had nothing listening — producing the generic network error.

### Issue 2 — `argon2-cffi` missing from `requirements.txt`

`app/security.py` imports `from argon2 import PasswordHasher` but `requirements.txt` did not list `argon2-cffi`. The package was already installed in the environment, so the backend ran fine, but `pip install -r requirements.txt` in a fresh environment would fail.

### Issue 3 — Stale port in CORS origins

`apps/api/.env` listed `http://localhost:8080` in `CORS_ORIGINS`. Port 8080 is not used by anything, so this was dead configuration. Removed.

### Issue 4 — `--reload` flag breaks on Windows (Microsoft Store Python)

When uvicorn's WatchFiles reloader spawns its worker subprocess, it does not inherit `sys.path` or `PYTHONPATH` set in the parent process. This is a Microsoft Store Python sandboxing behaviour. Running with `--reload` produced:

```
ERROR: Error loading ASGI app. Attribute "app" not found in module "main"
```

Running without `--reload` works correctly. The `run.py` launcher was updated to disable reload.

---

## Fixes Applied

### 1. `apps/web/.env.local`
```diff
-NEXT_PUBLIC_API_URL=http://127.0.0.1:8080
-NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8080
+NEXT_PUBLIC_API_URL=http://localhost:8000
+NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 2. `apps/api/requirements.txt`
```diff
 passlib[bcrypt]>=1.7.4
+argon2-cffi>=23.1.0
```

### 3. `apps/api/.env`
```diff
-CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080
+CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 4. `apps/api/run.py` (new file)
Created a proper Python launcher that ensures the `api/` directory is on `sys.path` before handing off to uvicorn — and disables `--reload` to work correctly on Windows with Microsoft Store Python.

### 5. `start-dev.ps1`
Updated to use `python run.py` instead of `python -m uvicorn main:app --reload ...`.

---

## How to Start the Backend

```powershell
# From the repo root:
powershell -ExecutionPolicy Bypass -File start-dev.ps1

# Or manually:
cd apps/api
python run.py
```

The backend starts on `http://localhost:8000`.

---

## Verification Results

### ✅ Backend starts without errors
```json
{"level":"INFO","message":"Starting CodeForge AI API Gateway..."}
{"level":"INFO","message":"Database tables created (create_all)"}
{"level":"INFO","message":"Admin user already exists — skipping seed"}
{"level":"INFO","message":"API ready — DB: SQLite"}
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### ✅ GET /api/v1/health/
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "1.0.0",
    "env": "development",
    "database": "healthy",
    "redis": "disabled",
    "kafka": "disabled"
  }
}
```

### ✅ POST /api/v1/auth/login
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### ✅ JWT structure verified
The access token decodes to:
```json
{
  "sub": "admin",
  "role": "admin",
  "user_id": "<uuid>",
  "type": "access",
  "exp": <timestamp>
}
```
This matches exactly what `apps/web/src/lib/auth.ts` expects (`DecodedToken` interface).

### ✅ CORS configured correctly
`CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000` — matches the frontend origin.

### ✅ GET /docs
FastAPI Swagger UI available at `http://localhost:8000/docs`.

---

## Authentication Flow (End-to-End)

```
Browser (localhost:3000)
  → POST http://localhost:8000/api/v1/auth/login
  ← { access_token, refresh_token, token_type, expires_in }
  → localStorage.setItem('cf_access_token', ...)
  → document.cookie = 'cf_access_token=...'
  → router.push('/')
  → Dashboard loads
```

The `api.ts` client automatically attaches `Authorization: Bearer <token>` to all subsequent requests.  
Token refresh is handled transparently via `POST /api/v1/auth/refresh`.

---

## Default Credentials

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |
| Role | `admin` |

These are seeded automatically on first startup via the `SEED_ADMIN_*` env vars in `apps/api/.env`.

---

## Architecture Notes

- **Database:** SQLite (`codeforge_dev.db`) for local dev — no external DB required
- **Redis:** Disabled (`REDIS_DISABLED=true`) — token blacklisting skipped locally
- **Kafka:** Disabled (`KAFKA_DISABLED=true`)
- **Password hashing:** Argon2 (via `argon2-cffi`)
- **JWT:** HS256, signed with `SECRET_KEY` from `.env`, 60-minute access tokens, 7-day refresh tokens
