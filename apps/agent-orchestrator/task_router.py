import logging
from typing import Dict, Any, Optional, List
from event_publisher import KafkaEventPublisher

logger = logging.getLogger("agent-orchestrator.task-router")

class TaskRouter:
    def __init__(self, event_pub: Optional[KafkaEventPublisher] = None, max_retries: int = 3, config_routing_map: Optional[Dict[str, str]] = None):
        self.max_retries = max_retries
        self.event_pub = event_pub
        
        # Default workflow state transition pipeline
        self.state_routing_map = config_routing_map or {
            "CREATED": "PLANNING",
            "PLANNING": "RESEARCHING",
            "RESEARCHING": "ARCHITECTING",
            "ARCHITECTING": "DATABASE_DESIGN",
            "DATABASE_DESIGN": "BACKEND_GENERATION",
            "BACKEND_GENERATION": "FRONTEND_GENERATION",
            "FRONTEND_GENERATION": "TESTING",
            "TESTING": "SECURITY_REVIEW",
            "SECURITY_REVIEW": "DEVOPS_GENERATION",
            "DEVOPS_GENERATION": "APPROVAL_PENDING",
            "APPROVAL_PENDING": "DEPLOYING",
            "DEPLOYING": "OBSERVABILITY",
            "OBSERVABILITY": "COST_OPTIMIZATION",
            "COST_OPTIMIZATION": "AUTONOMOUS_CONTROLLER",
            "AUTONOMOUS_CONTROLLER": "FINAL_DEPLOYMENT",
            "FINAL_DEPLOYMENT": "COMPLETED"
        }
        
        # Mapping from state to specialized executing agent
        self.state_agent_map = {
            "PLANNING": "ProductManagerAgent",
            "RESEARCHING": "ResearchAgent",
            "ARCHITECTING": "ArchitectAgent",
            "DATABASE_DESIGN": "DatabaseAgent",
            "BACKEND_GENERATION": "BackendAgent",
            "FRONTEND_GENERATION": "FrontendAgent",
            "TESTING": "QAAgent",
            "SECURITY_REVIEW": "SecurityAgent",
            "DEVOPS_GENERATION": "DevOpsAgent",
            "DEPLOYING": "DeploymentAgent",
            "OBSERVABILITY": "ObservabilityAgent",
            "COST_OPTIMIZATION": "CostOptimizationAgent",
            "AUTONOMOUS_CONTROLLER": "AutonomousControllerAgent",
            "FINAL_DEPLOYMENT": "DevOpsAgent"
        }

    def get_next_state(self, current_state: str, context: Dict[str, Any]) -> str:
        """
        Determines the next workflow state, factoring in errors and rework loops.
        """
        # TESTING rework loop: if QA testing failed with errors, route back to BACKEND_GENERATION
        if current_state == "TESTING" and context.get("errors"):
            logger.info("Test failures detected. Routing back to BACKEND_GENERATION for rework.")
            return "BACKEND_GENERATION"
            
        # Progressive routing mapping
        next_state = self.state_routing_map.get(current_state, "COMPLETED")
        logger.info(f"Routing state transition: {current_state} -> {next_state}")
        return next_state

    def get_assigned_agent(self, state: str) -> Optional[str]:
        return self.state_agent_map.get(state)

    def process_task_failure(self, task_id: str, workflow_id: str, retry_count: int, error_message: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates retry policies and dead-letter actions for failing tasks.
        If retry_count is less than max_retries, it suggests RETRY.
        If it reaches max_retries, it routes the message to the Dead-Letter Queue (DLQ).
        """
        if retry_count < self.max_retries:
            next_retry = retry_count + 1
            backoff_delay = 2 ** next_retry  # Exponential backoff
            logger.warning(f"Task {task_id} failed. Scheduling retry #{next_retry} in {backoff_delay}s. Error: {error_message}")
            return {
                "action": "RETRY",
                "retry_count": next_retry,
                "backoff_seconds": backoff_delay
            }
        else:
            logger.error(f"Task {task_id} reached maximum retry limit ({self.max_retries}). Routing to Dead-Letter Queue (DLQ).")
            if self.event_pub:
                self.event_pub.dead_letter(
                    original_topic="agent.tasks",
                    payload={
                        "task_id": task_id,
                        "workflow_id": workflow_id,
                        "payload": payload
                    },
                    reason=f"Max retries reached. Last error: {error_message}"
                )
            return {
                "action": "DEAD_LETTER",
                "error": error_message
            }
