import json
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import redis
from app.models import Workflow, WorkflowState

logger = logging.getLogger("agent-orchestrator.checkpoint-manager")

_STATE_TO_STATUS = {
    "CREATED":               "CREATED",
    "PLANNING":              "RUNNING",
    "RESEARCHING":           "RUNNING",
    "ARCHITECTING":          "RUNNING",
    "DATABASE_DESIGN":       "RUNNING",
    "BACKEND_GENERATION":    "RUNNING",
    "FRONTEND_GENERATION":   "RUNNING",
    "TESTING":               "RUNNING",
    "SECURITY_REVIEW":       "RUNNING",
    "DEVOPS_GENERATION":     "RUNNING",
    "APPROVAL_PENDING":      "PAUSED",
    "DEPLOYING":             "RUNNING",
    "OBSERVABILITY":         "RUNNING",
    "COST_OPTIMIZATION":     "RUNNING",
    "AUTONOMOUS_CONTROLLER": "RUNNING",
    "FINAL_DEPLOYMENT":      "RUNNING",
    "COMPLETED":             "COMPLETED",
    "FAILED":                "FAILED",
    "CANCELLED":             "CANCELLED",
    "PAUSED":                "PAUSED",
    "INITIATED":             "CREATED",
}

class CheckpointManager:
    def __init__(self, db_url: str, redis_url: str):
        # Convert async driver dialects if present for sync sqlalchemy engine
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.redis_url = redis_url
        self.redis_client = None
        
        # Initialize Redis connection with fallback to None
        try:
            self.redis_client = redis.Redis.from_url(
                redis_url, 
                socket_connect_timeout=1.0,
                socket_timeout=1.0
            )
            self.redis_client.ping()
            logger.info("Redis Hot Cache initialized successfully.")
        except Exception as e:
            logger.warning(f"Redis Hot Cache unavailable (falling back to direct DB): {e}")
            self.redis_client = None

    def save_checkpoint(
        self,
        workflow_id: str,
        current_node: str,
        execution_context: Dict[str, Any],
        agent_outputs: Dict[str, Any],
        errors: Optional[list] = None,
        human_approvals: Optional[list] = None
    ) -> int:
        """
        Saves workflow state checkpointer to Redis and PostgreSQL.
        Returns the version index representing this state.
        """
        state_payload = {
            "current_node": current_node,
            "execution_context": execution_context,
            "agent_outputs": agent_outputs,
            "errors": errors or [],
            "human_approvals": human_approvals or [],
            "saved_at": datetime.utcnow().isoformat()
        }

        # 1. Hot Cache Update (Redis)
        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"workflow:checkpoint:{workflow_id}",
                    3600,  # 1 hour expiration
                    json.dumps(state_payload)
                )
            except Exception as e:
                logger.warning(f"Failed to write to Redis hot cache: {e}")

        # 2. Database Cold Storage (Postgres)
        session = self.SessionLocal()
        try:
            # Get latest checkpoint to ensure strict monotonic entered_at ordering (avoids SQLite identical timestamp sorting issues)
            last_state = (
                session.query(WorkflowState)
                .filter(WorkflowState.workflow_id == uuid.UUID(workflow_id))
                .order_by(WorkflowState.entered_at.desc())
                .first()
            )
            entered_time = datetime.utcnow()
            if last_state and last_state.entered_at:
                from datetime import timedelta
                # Force datetime timezone offset removal if present to avoid compare error
                last_time = last_state.entered_at.replace(tzinfo=None) if last_state.entered_at.tzinfo else last_state.entered_at
                min_time = last_time + timedelta(milliseconds=1)
                if entered_time < min_time:
                    entered_time = min_time

            # Mark other active states as exited
            session.query(WorkflowState).filter(
                WorkflowState.workflow_id == uuid.UUID(workflow_id),
                WorkflowState.exited_at == None
            ).update({
                WorkflowState.exited_at: entered_time
            }, synchronize_session=False)

            # Insert new versioned checkpoint
            new_state = WorkflowState(
                workflow_id=uuid.UUID(workflow_id),
                state=current_node,
                metadata_json=state_payload,
                entered_at=entered_time
            )
            session.add(new_state)

            # Update master workflow record
            status = _STATE_TO_STATUS.get(current_node, "RUNNING")
            session.query(Workflow).filter(
                Workflow.workflow_id == uuid.UUID(workflow_id)
            ).update({
                Workflow.current_state: current_node,
                Workflow.status: status,
                Workflow.updated_at: datetime.utcnow()
            }, synchronize_session=False)

            session.commit()
            
            # Count historical states as versioning index
            version_count = session.query(WorkflowState).filter(
                WorkflowState.workflow_id == uuid.UUID(workflow_id)
            ).count()
            
            logger.info(f"Saved checkpoint version {version_count} for workflow {workflow_id} at node '{current_node}'")
            return version_count
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to persist SQL checkpoint for {workflow_id}: {e}")
            raise
        finally:
            session.close()

    def restore_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest checkpoint from Redis or PostgreSQL.
        """
        # 1. Check Hot Cache
        if self.redis_client:
            try:
                cached = self.redis_client.get(f"workflow:checkpoint:{workflow_id}")
                if cached:
                    logger.debug(f"Restored checkpoint for {workflow_id} from Redis hot cache.")
                    return json.loads(cached.decode("utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read from Redis cache: {e}")

        # 2. Fall back to Postgres
        session = self.SessionLocal()
        try:
            states = (
                session.query(WorkflowState)
                .filter(WorkflowState.workflow_id == uuid.UUID(workflow_id))
                .order_by(WorkflowState.entered_at.desc())
                .all()
            )
            for state in states:
                if state.metadata_json and isinstance(state.metadata_json, dict) and "current_node" in state.metadata_json:
                    logger.info(f"Restored checkpoint for {workflow_id} from PostgreSQL.")
                    return state.metadata_json
            return None
        except Exception as e:
            logger.error(f"Failed to query SQL checkpoint: {e}")
            return None
        finally:
            session.close()

    def rollback_checkpoint(self, workflow_id: str, target_state: str) -> bool:
        """
        Rolls back the workflow status to a specific node checkpoint.
        """
        session = self.SessionLocal()
        try:
            # Find the most recent historical record matching the target state node
            historical_state = (
                session.query(WorkflowState)
                .filter(
                    WorkflowState.workflow_id == uuid.UUID(workflow_id),
                    WorkflowState.state == target_state
                )
                .order_by(WorkflowState.entered_at.desc())
                .first()
            )
            if not historical_state:
                logger.warning(f"No checkpoint found matching state '{target_state}' for workflow {workflow_id}")
                return False

            # Delete any checkpoints entered after this target state's timestamp
            session.query(WorkflowState).filter(
                WorkflowState.workflow_id == uuid.UUID(workflow_id),
                WorkflowState.entered_at > historical_state.entered_at
            ).delete(synchronize_session=False)

            # Reset the target checkpoint to be active (no exited_at timestamp)
            historical_state.exited_at = None
            session.add(historical_state)

            # Sync master workflow status
            session.query(Workflow).filter(
                Workflow.workflow_id == uuid.UUID(workflow_id)
            ).update({
                Workflow.current_state: target_state,
                Workflow.updated_at: datetime.utcnow()
            }, synchronize_session=False)

            session.commit()
            
            # Sync hot cache
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        f"workflow:checkpoint:{workflow_id}",
                        3600,
                        json.dumps(historical_state.metadata_json)
                    )
                except Exception as cache_err:
                    logger.warning(f"Failed to update Redis during rollback: {cache_err}")
            
            logger.info(f"Rolled back workflow {workflow_id} successfully to state checkpoint '{target_state}'")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed checkpoint rollback for {workflow_id}: {e}")
            return False
        finally:
            session.close()
