import os
import sys
import time
import logging
import threading
import signal
from typing import Dict, Any

from fastapi import FastAPI

# Add workspaces path to PYTHONPATH to allow imports of app models and api packages
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
api_path = os.path.join(workspace_root, "apps", "api")
orchestrator_path = os.path.join(workspace_root, "apps", "agent-orchestrator")
if api_path not in sys.path:
    sys.path.insert(0, api_path)
if orchestrator_path not in sys.path:
    sys.path.insert(0, orchestrator_path)

from app.database import Base
from app.models import ApprovalRequest, ApprovalEscalation
from app.repositories.approval import (
    ApprovalRequestRepository,
    ApprovalEscalationRepository,
    ApprovalAuditLogRepository
)
from app.repositories.workflow import WorkflowRepository, WorkflowStateRepository
from app.services.approval import ApprovalAuditService, EscalationManager
from event_publisher import KafkaEventPublisher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s", "logger":"%(name)s"}'
)
logger = logging.getLogger("approval-service.main")

# FastAPI App for Health checks and service information
app = FastAPI(
    title="CodeForge AI - Approval Service",
    description="Manages workflow pauses, notifications, and signature audits for human approvals",
    version="1.0.0"
)

# Global run loop state
running = True

@app.get("/healthz", status_code=200)
async def health_check():
    return {"status": "healthy", "service": "approval-service"}

def handle_approval_requested(payload: Dict[str, Any]):
    """
    Kafka consumer callback when a new approval is requested.
    Evaluates channels and triggers alerts.
    """
    approval_id = payload.get("approval_id")
    workflow_id = payload.get("workflow_id")
    approval_type = payload.get("approval_type")
    target_role = payload.get("target_role")

    logger.info(f"[Consumer Event] Processing approval.requested for {approval_id} (Type: {approval_type})")

    # Send dynamic notifications
    message = f"NOTIFICATION: Workflow {workflow_id} is WAITING_FOR_APPROVAL ({approval_type}). Reviewer: {target_role}"
    
    # 1. Slack notification simulation
    logger.info(f"[Alert Channel - Slack] Pushing webhook alert to #governance-approvals: {message}")
    
    # 2. Email notification simulation
    logger.info(f"[Alert Channel - Email] Sending dispatch mail to role group {target_role}@codeforge.ai: {message}")
    
    # 3. SSE Notification simulation
    logger.info(f"[Alert Channel - SSE] Broadcasting Server-Sent Event to dashboard client active streams")

def run_escalation_loop(db_url: str, kafka_servers: str):
    """
    Background scheduler loop that scans for expired approvals and escalates them.
    """
    logger.info("Starting background Escalation Manager daemon scheduler...")
    
    # Clean DB url for sync engine
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif db_url.startswith("sqlite+aiosqlite://"):
        db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    
    event_pub = KafkaEventPublisher(bootstrap_servers=kafka_servers)
    
    while running:
        session = SessionLocal()
        try:
            req_repo = ApprovalRequestRepository(session)
            esc_repo = ApprovalEscalationRepository(session)
            state_repo = WorkflowStateRepository(session)
            wf_repo = WorkflowRepository(session)
            audit_repo = ApprovalAuditLogRepository(session)
            audit_service = ApprovalAuditService(audit_repo)

            esc_manager = EscalationManager(
                request_repo=req_repo,
                escalation_repo=esc_repo,
                state_repo=state_repo,
                workflow_repo=wf_repo,
                audit_service=audit_service,
                event_pub=event_pub
            )

            # Perform scan
            escalated_count = session.query(ApprovalEscalation).filter(ApprovalEscalation.status == "PENDING").count()
            if escalated_count > 0:
                logger.info(f"Scanning {escalated_count} pending escalations...")
                escalated = session.execute(
                    session.query(ApprovalEscalation).filter(ApprovalEscalation.status == "PENDING").statement
                ).scalars().all()
                # Run sync scan and escalate
                await_res = esc_manager.scan_and_escalate()
                if await_res > 0:
                    session.commit()
                    logger.info(f"Escalated {await_res} approvals successfully.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error during escalation scanning: {e}")
        finally:
            session.close()
        
        # Poll interval: 10 seconds
        time.sleep(10)

def start_background_consumer(kafka_servers: str):
    """
    Subscribes to approval events topic.
    """
    event_pub = KafkaEventPublisher(bootstrap_servers=kafka_servers)
    
    def consumer_cb(payload: Dict[str, Any]):
        if payload.get("event_type") == "approval.requested":
            handle_approval_requested(payload)

    def stop_check() -> bool:
        return not running

    try:
        event_pub.start_consumer(
            topic="approval.events",
            group_id="approval-service-group",
            callback=consumer_cb,
            stop_check=stop_check
        )
    except Exception as e:
        logger.error(f"Approval consumer failed or terminated: {e}")

def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal caught. Graceful exit...")
    running = False

def start_daemons():
    # Setup signal traps
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:secure_password@localhost:5432/codeforge")
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Start Escalation loop thread
    esc_thread = threading.Thread(target=run_escalation_loop, args=(db_url, kafka_servers), daemon=True)
    esc_thread.start()

    # Start Kafka Consumer loop thread
    consumer_thread = threading.Thread(target=start_background_consumer, args=(kafka_servers,), daemon=True)
    consumer_thread.start()

# Start background daemons on import or startup
if os.getenv("RUN_DAEMONS", "false").lower() == "true":
    start_daemons()
