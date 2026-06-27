import logging
import json
import time
import uuid
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.config import settings
from app.database import engine, AsyncSessionLocal, Base
from app.exceptions import register_exception_handlers
from app.middleware import RequestIdMiddleware, SecurityHeadersMiddleware

# ── Logging ─────────────────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

root_logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
root_logger.handlers = [handler]
root_logger.setLevel(logging.INFO)
logging.getLogger("uvicorn.access").disabled = True

logger = logging.getLogger("api-gateway")

# ── Prometheus ───────────────────────────────────────────────────────────────
try:
    from prometheus_client import make_asgi_app, Counter, Histogram
    REQUEST_COUNT = Counter(
        "codeforge_api_requests_total",
        "Total number of HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "codeforge_api_request_latency_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
    )
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False
    logger.warning("prometheus_client not installed — metrics disabled")

# ── DB Init + Seed ───────────────────────────────────────────────────────────
async def init_db_and_seed():
    """Create all tables and seed the admin user if it doesn't exist."""
    from app.models import User  # noqa: import all models so Base knows about them
    import importlib, pkgutil, app.models as models_module  # ensure all models loaded

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (create_all)")

    # Seed admin user
    try:
        from app.security import get_password_hash

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.username == settings.SEED_ADMIN_USERNAME)
            )
            existing = result.scalar_one_or_none()
            if not existing:
                admin = User(
                    user_id=uuid.uuid4(),
                    username=settings.SEED_ADMIN_USERNAME,
                    email=settings.SEED_ADMIN_EMAIL,
                    password_hash=get_password_hash(settings.SEED_ADMIN_PASSWORD),
                    role="admin",
                    is_verified=True,
                )
                session.add(admin)
                await session.commit()
                logger.info(f"Seeded admin user: {settings.SEED_ADMIN_USERNAME}")
            else:
                logger.info("Admin user already exists — skipping seed")
    except Exception as e:
        logger.warning(f"Seed failed (non-fatal): {e}")

# ── Lifespan ─────────────────────────────────────────────────────────────────
# Helper to dynamically import and run a python file main function in background thread
def load_and_start_module(filepath: str, module_name: str):
    import importlib.machinery
    import importlib.util
    import threading
    import sys
    
    logger.info(f"Dynamically loading {module_name} from {filepath}")
    # Add parent directory of module to sys.path so nested imports work
    dir_path = os.path.dirname(filepath)
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)
        
    loader = importlib.machinery.SourceFileLoader(module_name, filepath)
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    
    if hasattr(module, "main"):
        t = threading.Thread(target=module.main, daemon=True, name=f"Thread-{module_name}")
        t.start()
        logger.info(f"Started daemon thread for {module_name}")
    else:
        logger.error(f"Module {module_name} has no main() function")

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    logger.info("Starting CodeForge AI API Gateway...")
    await init_db_and_seed()
    logger.info(f"API ready — DB: {'SQLite' if settings.is_sqlite else 'PostgreSQL'}")
    
    if settings.KAFKA_DISABLED:
        logger.info("KAFKA_DISABLED is True. Launching local orchestrator and agent workers in background threads...")
        os.environ["DATABASE_URL"] = settings.DATABASE_URL
        os.environ["KAFKA_DISABLED"] = "true"
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        orchestrator_main_path = os.path.join(base_dir, "agent-orchestrator", "main.py")
        workers_main_path = os.path.join(base_dir, "agent-workers", "main.py")
        
        try:
            load_and_start_module(orchestrator_main_path, "agent_orchestrator_main")
        except Exception as e:
            logger.error(f"Failed to start local orchestrator thread: {e}")
            
        try:
            load_and_start_module(workers_main_path, "agent_workers_main")
        except Exception as e:
            logger.error(f"Failed to start local agent workers thread: {e}")
            
    yield
    logger.info("Shutting down API Gateway...")
    await engine.dispose()

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Autonomous SDLC Platform — API Gateway",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

register_exception_handlers(app)

# Middlewares (order matters — added last = executes first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Telemetry ─────────────────────────────────────────────────────────
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    req_id = getattr(request.state, "request_id", "unknown")

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    status_code = response.status_code

    if PROMETHEUS_ENABLED:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    return response

# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers import (
    auth, project, health, enterprise, workflow, approval,
    database, backend, frontend, qa, security, devops,
    collaboration, observability, cost, controller,
)

PREFIX = f"/api/{settings.API_VERSION}"
app.include_router(health.router,         prefix=PREFIX)
app.include_router(auth.router,           prefix=PREFIX)
app.include_router(project.router,        prefix=PREFIX)
app.include_router(enterprise.router,     prefix=PREFIX)
app.include_router(workflow.router,       prefix=PREFIX)
app.include_router(approval.router,       prefix=PREFIX)
app.include_router(database.router,       prefix=PREFIX)
app.include_router(backend.router,        prefix=PREFIX)
app.include_router(frontend.router,       prefix=PREFIX)
app.include_router(qa.router,             prefix=PREFIX)
app.include_router(security.router,       prefix=PREFIX)
app.include_router(devops.router,         prefix=PREFIX)
app.include_router(collaboration.router,  prefix=PREFIX)
app.include_router(observability.router,  prefix=PREFIX)
app.include_router(cost.router,           prefix=PREFIX)
app.include_router(controller.router,     prefix=PREFIX)

# ── Prometheus Metrics Mount ──────────────────────────────────────────────────
if PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    return {
        "success": True,
        "data": {
            "service": settings.PROJECT_NAME,
            "version": "1.0.0",
            "env": settings.ENV,
            "docs": "/docs",
            "health": f"{PREFIX}/health",
            "metrics": "/metrics" if PROMETHEUS_ENABLED else "disabled",
        },
        "error": None,
    }
