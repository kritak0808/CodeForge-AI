import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Workflow, WorkflowState
from checkpoint_manager import CheckpointManager

logger = logging.getLogger("agent-orchestrator.recovery-manager")

class RecoveryManager:
    def __init__(self, db_url: str, checkpoint_mgr: CheckpointManager, max_rework_cycles: int = 3):
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
        self.checkpoint_mgr = checkpoint_mgr
        self.max_rework_cycles = max_rework_cycles

    def recover_interrupted_workflows(self) -> int:
        """
        Scans database on gateway startup for unfinished workflow states and recovers them.
        """
        session = self.SessionLocal()
        recovered_count = 0
        try:
            # Active states that are not final (COMPLETED, FAILED, CANCELLED)
            active_workflows = (
                session.query(Workflow)
                .filter(Workflow.current_state.notin_(["COMPLETED", "FAILED", "CANCELLED"]))
                .all()
            )
            
            for wf in active_workflows:
                logger.info(f"Recovering interrupted workflow {wf.workflow_id} from checkpoint...")
                checkpoint_data = self.checkpoint_mgr.restore_checkpoint(str(wf.workflow_id))
                if checkpoint_data:
                    # Reset current state to the last checkpoint's node
                    last_node = checkpoint_data.get("current_node", "INITIATED")
                    wf.current_state = last_node
                    wf.updated_at = datetime.utcnow()
                    recovered_count += 1
                    logger.info(f"Workflow {wf.workflow_id} successfully restored to node '{last_node}'")
                else:
                    # Force transition to FAILED if no checkpoint can be restored
                    wf.current_state = "FAILED"
                    logger.warning(f"No checkpoint found for workflow {wf.workflow_id}. Marked as FAILED.")
            
            session.commit()
            return recovered_count
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to execute startup workflows recovery: {e}")
            return 0
        finally:
            session.close()

    def check_circuit_breaker(self, workflow_id: str, current_state: str, execution_context: Dict[str, Any]) -> bool:
        """
        Checks if the workflow has entered a runaway loop (e.g. backend code compilation and QA failures loop).
        Returns True if the breaker is open (workflow should fail), False otherwise.
        """
        # Count rework cycles in execution context
        rework_cycles = execution_context.get("rework_cycles", {})
        cycle_count = rework_cycles.get(current_state, 0)
        
        if cycle_count >= self.max_rework_cycles:
            logger.error(
                f"Circuit breaker tripped for workflow {workflow_id} at state '{current_state}'. "
                f"Exceeded maximum rework cycles limit ({self.max_rework_cycles})."
            )
            return True
            
        return False

    def increment_rework_cycle(self, execution_context: Dict[str, Any], state: str) -> Dict[str, Any]:
        """
        Helper to increment the cycle tracker inside context object.
        """
        if "rework_cycles" not in execution_context:
            execution_context["rework_cycles"] = {}
        
        cycles = execution_context["rework_cycles"]
        cycles[state] = cycles.get(state, 0) + 1
        return execution_context
