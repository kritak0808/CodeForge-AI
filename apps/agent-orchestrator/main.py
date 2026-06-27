import os
import sys
import time
import logging
import signal
from typing import Dict, Any

# Ensure import of parent app models is possible
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
api_path = os.path.join(workspace_root, "apps", "api")
if api_path not in sys.path:
    sys.path.insert(0, api_path)

from event_publisher import KafkaEventPublisher
from workflow_manager import WorkflowManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s", "logger":"%(name)s"}'
)
logger = logging.getLogger("agent-orchestrator.main")

# Global stop flag for graceful shutdown
running = True

def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Stopping consumer loops...")
    running = False

def process_workflow_event(payload: Dict[str, Any], manager: WorkflowManager):
    """
    Consumer callback to process workflow events and progress state machines asynchronously.
    """
    event_type = payload.get("event_type")
    workflow_id = payload.get("workflow_id")
    logger.info(f"Processing workflow event: {event_type} for workflow {workflow_id}")
    if event_type == "TRIGGER_STATE_STEP":
        try:
            manager.resume_workflow(workflow_id)
        except Exception as e:
            logger.error(f"Failed to progress workflow {workflow_id}: {e}")
    elif event_type == "database.design.completed":
        manager.on_database_design_completed(
            workflow_id=workflow_id,
            design_id=payload.get("design_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "database.design.failed":
        manager.on_database_design_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown database design error"),
        )
    elif event_type == "backend.generation.completed":
        manager.on_backend_generation_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "backend.generation.failed":
        manager.on_backend_generation_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown backend generation error"),
        )
    elif event_type == "frontend.generation.completed":
        manager.on_frontend_generation_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "frontend.generation.failed":
        manager.on_frontend_generation_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown frontend generation error"),
        )
    elif event_type == "qa.generation.completed":
        manager.on_qa_generation_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary"),
            errors=payload.get("errors"),
        )
    elif event_type == "qa.generation.failed":
        manager.on_qa_generation_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown QA generation error"),
        )
    elif event_type == "security.generation.completed":
        manager.on_security_generation_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "security.generation.failed":
        manager.on_security_generation_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown Security generation error"),
        )
    elif event_type == "devops.generation.completed":
        manager.on_devops_generation_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "devops.generation.failed":
        manager.on_devops_generation_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown DevOps generation error"),
        )
    elif event_type == "agent.review.requested":
        manager.on_agent_review_requested(
            session_id=payload.get("session_id"),
            review_id=payload.get("review_id"),
            reviewer_agent=payload.get("reviewer_agent"),
            target_agent=payload.get("target_agent"),
            artifact_type=payload.get("artifact_type"),
            artifact_id=payload.get("artifact_id"),
        )
    elif event_type == "agent.review.completed":
        manager.on_agent_review_completed(
            session_id=payload.get("session_id"),
            review_id=payload.get("review_id"),
            reviewer_agent=payload.get("reviewer_agent"),
            status=payload.get("status"),
        )
    elif event_type == "agent.vote.completed":
        manager.on_agent_vote_completed(
            session_id=payload.get("session_id"),
            topic=payload.get("topic"),
            voter_agent=payload.get("voter_agent"),
            decision=payload.get("decision"),
        )
    elif event_type == "agent.conflict.resolved":
        manager.on_agent_conflict_resolved(
            session_id=payload.get("session_id"),
            conflict_id=payload.get("conflict_id"),
            resolved_by=payload.get("resolved_by"),
            strategy=payload.get("strategy"),
        )
    elif event_type == "agent.collaboration.completed":
        manager.on_agent_collaboration_completed(
            workflow_id=payload.get("workflow_id"),
            session_id=payload.get("session_id"),
        )
    elif event_type == "observability.completed":
        manager.on_observability_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary", {}),
        )
    elif event_type == "observability.generation.failed":
        manager.on_observability_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown observability generation error"),
        )
    elif event_type == "cost.analysis.completed":
        manager.on_cost_analysis_completed(
            workflow_id=workflow_id,
            generation_id=payload.get("generation_id"),
            result_summary=payload.get("result_summary", {}),
        )
    elif event_type == "cost.analysis.failed":
        manager.on_cost_analysis_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown cost optimization error"),
        )
    elif event_type == "controller.completed":
        manager.on_controller_completed(
            workflow_id=workflow_id,
            controller_id=payload.get("controller_id"),
            result_summary=payload.get("result_summary"),
        )
    elif event_type == "controller.retry":
        manager.on_controller_retry(
            workflow_id=workflow_id,
            controller_id=payload.get("controller_id"),
            step=payload.get("step"),
            retry_attempt=payload.get("retry_attempt", 1),
        )
    elif event_type == "controller.rollback":
        manager.on_controller_rollback(
            workflow_id=workflow_id,
            controller_id=payload.get("controller_id"),
            source_step=payload.get("source_step"),
            target_step=payload.get("target_step"),
        )
    elif event_type == "controller.failed":
        manager.on_controller_failed(
            workflow_id=workflow_id,
            error=payload.get("error", "Unknown controller failure"),
        )

def main():
    global running
    # Register signal handlers for containers/k8s orchestrations
    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except ValueError:
        logger.warning("Signal handlers can only be set in the main thread. Skipping signal registration.")

    logger.info("Initializing CodeForge AI LangGraph Orchestrator Worker...")

    # Load environmental parameters
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:secure_password@localhost:5432/codeforge")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Initialize components
    event_pub = KafkaEventPublisher(bootstrap_servers=kafka_servers)
    manager = WorkflowManager(db_url=db_url, redis_url=redis_url, event_pub=event_pub)

    # Recover any crashed workflows on startup
    logger.info("Scanning for interrupted workflows to recover...")
    recovered = manager.recovery_mgr.recover_interrupted_workflows()
    logger.info(f"Successfully recovered {recovered} interrupted workflows.")

    # Start Kafka consumer loop in the main thread
    logger.info("Subscribing to Kafka workflow event topics...")
    
    def consumer_callback(payload: Dict[str, Any]):
        process_workflow_event(payload, manager)

    # Check if consumer should stop
    def should_stop() -> bool:
        return not running

    try:
        # Consumer starts block polling
        event_pub.start_consumer(
            topic=[
                "workflow.events",
                "database.design.events",
                "backend.generation.events",
                "frontend.generation.events",
                "qa.generation.events",
                "security.generation.events",
                "devops.generation.events",
                "agent.message.sent",
                "agent.review.requested",
                "agent.review.completed",
                "agent.vote.started",
                "agent.vote.completed",
                "agent.conflict.created",
                "agent.conflict.resolved",
                "agent.collaboration.completed",
                "observability.generation.events",
                "cost.generation.events",
                "controller.completed",
                "controller.retry",
                "controller.rollback",
                "controller.failed"
            ],
            group_id="agent-orchestrator-group",
            callback=consumer_callback,
            stop_check=should_stop
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user request.")
    except Exception as e:
        logger.error(f"Consumer loop failed or exited with error: {e}")

    logger.info("Orchestrator worker shutdown completed.")

if __name__ == "__main__":
    main()
