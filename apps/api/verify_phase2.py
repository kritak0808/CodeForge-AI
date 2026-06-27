"""Phase 2 verification script — run from apps/api directory."""
import urllib.request
import json
import sys


def api(path, method="GET", data=None, token=None):
    req = urllib.request.Request(
        f"http://localhost:8000/api/v1{path}", method=method
    )
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data else None
    try:
        r = urllib.request.urlopen(req, data=body, timeout=5)
        return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)


results = []

# 1. Health
r, e = api("/health/")
results.append(("GET /health", r is not None and r["data"]["status"] == "ok", e or r["data"]["status"]))

# 2. Login
r, e = api("/auth/login", "POST", {"username": "admin", "password": "admin123"})
token = r["data"]["access_token"] if r else None
results.append(("POST /auth/login", bool(token), e or "JWT returned"))

# 3. GET /workflows (new endpoint)
r, e = api("/workflows/", token=token)
results.append(("GET /workflows/", r is not None and r["success"], e or f"count={len(r['data'])}"))

# 4. POST /projects
r, e = api("/projects/", "POST",
           {"name": "Audit Test", "tech_stack": {"be": "FastAPI"}, "budget_usd_limit": 100},
           token=token)
pid = r["data"]["project_id"] if r else None
results.append(("POST /projects/", bool(pid), e or f"id={str(pid)[:8]}"))

# 5a. POST /workflows — no requirements (optional field)
r, e = api("/workflows/", "POST", {"project_id": pid}, token=token)
wid = r["data"]["workflow_id"] if r else None
status_val = r["data"]["status"] if r else None
results.append(("POST /workflows (no requirements)", bool(wid), e or f"status={status_val}"))

# 5b. POST /workflows — with requirements
r, e = api("/workflows/", "POST", {"project_id": pid, "requirements": "Build a todo app"}, token=token)
results.append(("POST /workflows (with requirements)", r is not None and r["success"], e or f"status={r['data']['status']}"))

# 6. GET /workflows?project_id=...
r, e = api(f"/workflows/?project_id={pid}", token=token)
results.append(("GET /workflows?project_id=...", r is not None, e or f"count={len(r['data'])}"))

# 7. enterprise stats — checks new status column queries
r, e = api("/enterprise/stats", token=token)
stats = r["data"] if r else {}
results.append(("GET /enterprise/stats", r is not None, e or json.dumps(stats)))

# 8. GET /approvals — no filter
r, e = api("/approvals/", token=token)
results.append(("GET /approvals/", r is not None, e or f"count={len(r['data'])}"))

# 9. GET /approvals?status=pending
r, e = api("/approvals/?status=pending", token=token)
results.append(("GET /approvals?status=pending", r is not None, e or f"count={len(r['data'])}"))

# 10. GET /cost/report
r, e = api("/cost/report", token=token)
results.append(("GET /cost/report", r is not None and r["success"], e or "ok"))

# 11. GET /observability/agents
r, e = api("/observability/agents", token=token)
results.append(("GET /observability/agents", r is not None and r["success"], e or f"count={len(r['data'])}"))

# 12. Token refresh
r2, _ = api("/auth/login", "POST", {"username": "admin", "password": "admin123"})
rt = r2["data"]["refresh_token"] if r2 else None
r, e = api("/auth/refresh", "POST", {"refresh_token": rt})
results.append(("POST /auth/refresh", r is not None and r["success"], e or "new token returned"))

# 13. GET /workflows/{id} — check new fields present
if wid:
    r, e = api(f"/workflows/{wid}", token=token)
    has_fields = (r is not None and
                  "status" in r["data"] and
                  "tasks_completed" in r["data"] and
                  "tasks_total" in r["data"])
    results.append(("GET /workflows/{id} has status/tasks fields", has_fields, e or "ok"))

# 14. GET /docs (swagger)
try:
    req = urllib.request.Request("http://localhost:8000/docs")
    resp = urllib.request.urlopen(req, timeout=3)
    results.append(("GET /docs (Swagger UI)", resp.status == 200, "ok"))
except Exception as ex:
    results.append(("GET /docs (Swagger UI)", False, str(ex)))

print()
print("=" * 65)
print("  PHASE 2 API VERIFICATION")
print("=" * 65)
all_pass = True
for name, passed, detail in results:
    icon = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{icon}] {name}")
    print(f"         {detail}")
print("=" * 65)
print(f"  RESULT: {'ALL TESTS PASSED' if all_pass else 'FAILURES DETECTED'}")
print(f"  {len([x for x in results if x[1]])}/{len(results)} tests passed")
print("=" * 65)

sys.exit(0 if all_pass else 1)
